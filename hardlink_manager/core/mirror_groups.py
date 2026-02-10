"""Mirror group registry: data model and JSON persistence."""

import json
import os
import platform
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


MIRROR_MARKER = ".hardlink_mirror"
"""Hidden file placed in each folder that belongs to a confirmed mirror group."""


def write_mirror_marker(folder: str, group_id: str) -> None:
    """Write a hidden marker file into *folder* to tag it as a mirror."""
    marker = os.path.join(folder, MIRROR_MARKER)
    try:
        with open(marker, "w", encoding="utf-8") as f:
            json.dump({"group_id": group_id}, f)
        if platform.system() == "Windows":
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(marker, 0x02)
    except OSError:
        pass


def has_mirror_marker(folder: str) -> bool:
    """Return True if *folder* contains a mirror marker file."""
    return os.path.isfile(os.path.join(folder, MIRROR_MARKER))


def read_mirror_marker(folder: str) -> Optional[str]:
    """Return the group-id stored in the marker, or None."""
    try:
        with open(os.path.join(folder, MIRROR_MARKER), "r", encoding="utf-8") as f:
            return json.load(f).get("group_id")
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def remove_mirror_marker(folder: str) -> None:
    """Remove the marker file from *folder* if it exists."""
    try:
        os.remove(os.path.join(folder, MIRROR_MARKER))
    except OSError:
        pass


@dataclass
class MirrorGroup:
    """A mirror group: a set of folders kept in sync via hardlinks."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    folders: list[str] = field(default_factory=list)
    sync_enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self):
        """Update the modified_at timestamp."""
        self.modified_at = datetime.now(timezone.utc).isoformat()

    def auto_name(self) -> str:
        """Generate a display name from folder basenames (e.g. 'Photos + Backup')."""
        if not self.folders:
            return "(empty)"
        names = [os.path.basename(f) or f for f in self.folders]
        return " + ".join(names)


DEFAULT_REGISTRY_FILENAME = "mirror_groups.json"


def _default_registry_path() -> str:
    """Return a stable path for the registry JSON file.

    Uses the OS-appropriate user data directory so the file persists
    across PyInstaller --onefile runs (where __file__ points to a
    temporary extraction directory that changes every launch).
    """
    import platform
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        data_dir = os.path.join(base, "HardlinkManager")
    elif system == "Darwin":
        data_dir = os.path.join(os.path.expanduser("~"),
                                "Library", "Application Support", "HardlinkManager")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
        data_dir = os.path.join(xdg, "hardlink_manager")
    return os.path.join(data_dir, DEFAULT_REGISTRY_FILENAME)


class MirrorGroupRegistry:
    """Persistent registry of mirror groups, backed by a JSON file."""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            path = _default_registry_path()
        self.path = os.path.abspath(path)
        self._groups: dict[str, MirrorGroup] = {}
        self.load()

    # -- Persistence --

    def load(self):
        """Load mirror groups from the JSON file."""
        self._groups.clear()
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data.get("groups", []):
                group = MirrorGroup(
                    id=entry.get("id", str(uuid.uuid4())),
                    name=entry.get("name", ""),
                    folders=entry.get("folders", []),
                    sync_enabled=entry.get("sync_enabled", True),
                    created_at=entry.get("created_at", ""),
                    modified_at=entry.get("modified_at", ""),
                )
                self._groups[group.id] = group
        except (json.JSONDecodeError, OSError):
            pass

    def save(self):
        """Save mirror groups to the JSON file."""
        data = {
            "groups": [asdict(g) for g in self._groups.values()]
        }
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # -- CRUD --

    def create_group(self, folders: list[str],
                     sync_enabled: bool = True,
                     name: str = "") -> MirrorGroup:
        """Create a new mirror group and save. Name is auto-generated from folders if empty."""
        group = MirrorGroup(name=name, folders=folders, sync_enabled=sync_enabled)
        if not group.name:
            group.name = group.auto_name()
        self._groups[group.id] = group
        self.save()
        for f in group.folders:
            write_mirror_marker(f, group.id)
        return group

    def get_group(self, group_id: str) -> Optional[MirrorGroup]:
        return self._groups.get(group_id)

    def get_all_groups(self) -> list[MirrorGroup]:
        return list(self._groups.values())

    def update_group(self, group_id: str, name: Optional[str] = None,
                     folders: Optional[list[str]] = None,
                     sync_enabled: Optional[bool] = None) -> Optional[MirrorGroup]:
        """Update an existing mirror group and save. Name is auto-updated when folders change."""
        group = self._groups.get(group_id)
        if group is None:
            return None
        if name is not None:
            group.name = name
        if folders is not None:
            old_set = set(group.folders)
            new_set = set(folders)
            for removed in old_set - new_set:
                remove_mirror_marker(removed)
            group.folders = folders
            group.name = group.auto_name()
            for added in new_set - old_set:
                write_mirror_marker(added, group_id)
        if sync_enabled is not None:
            group.sync_enabled = sync_enabled
        group.touch()
        self.save()
        return group

    def delete_group(self, group_id: str) -> bool:
        """Delete a mirror group and save. Returns True if it existed."""
        group = self._groups.get(group_id)
        if group is not None:
            for f in group.folders:
                remove_mirror_marker(f)
            del self._groups[group_id]
            self.save()
            return True
        return False

    def clear_all_groups(self) -> int:
        """Remove all mirror groups and their markers. Returns the count removed."""
        count = len(self._groups)
        for group in self._groups.values():
            for f in group.folders:
                remove_mirror_marker(f)
        self._groups.clear()
        self.save()
        return count

    def add_folder_to_group(self, group_id: str, folder: str) -> bool:
        """Add a folder to a mirror group. Returns True on success."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        folder = os.path.abspath(folder)
        if folder not in group.folders:
            group.folders.append(folder)
            group.name = group.auto_name()
            group.touch()
            self.save()
            write_mirror_marker(folder, group_id)
        return True

    def remove_folder_from_group(self, group_id: str, folder: str) -> bool:
        """Remove a folder from a mirror group. Returns True on success."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        folder = os.path.abspath(folder)
        if folder in group.folders:
            group.folders.remove(folder)
            group.name = group.auto_name()
            group.touch()
            self.save()
            remove_mirror_marker(folder)
            return True
        return False

    # -- Queries --

    def find_group_for_folder(self, folder: str) -> Optional[MirrorGroup]:
        """Find the mirror group that contains the given folder, if any."""
        folder = os.path.normpath(os.path.abspath(folder))
        for group in self._groups.values():
            for gf in group.folders:
                if os.path.normpath(os.path.abspath(gf)) == folder:
                    return group
        return None

    def find_group_for_path(self, path: str) -> Optional[tuple["MirrorGroup", str]]:
        """Find the mirror group that contains a path (file or subfolder).

        Returns (group, group_folder) where group_folder is the top-level
        folder that is a parent of path, or None if no match.
        """
        path = os.path.normpath(os.path.abspath(path))
        for group in self._groups.values():
            for gf in group.folders:
                norm_gf = os.path.normpath(os.path.abspath(gf))
                # path is inside (or equal to) this group folder
                if path == norm_gf or path.startswith(norm_gf + os.sep):
                    return (group, norm_gf)
        return None

    def is_folder_in_group(self, folder: str) -> bool:
        """Check if a folder belongs to any mirror group."""
        return self.find_group_for_folder(folder) is not None

    def quick_scan_mirrors(
        self,
        root_folders: list[str],
        progress_callback: Optional["Callable[[int, int], None]"] = None,
    ) -> list["MirrorGroup"]:
        """Quick scan: discover mirror groups from existing marker files only.

        Walks each root folder recursively looking for ``.hardlink_mirror``
        manifest files.  Folders that share the same ``group_id`` in their
        marker are grouped together.  Only groups not already registered
        are created.

        This is much faster than a full content scan because it skips
        file hashing entirely -- it only checks for the presence and
        content of marker files.

        The *progress_callback*, if provided, is called periodically with
        ``(directories_scanned, markers_found)``.

        Returns:
            List of newly created :class:`MirrorGroup` objects.
        """
        root_folders = [os.path.normpath(os.path.abspath(f))
                        for f in root_folders if os.path.isdir(f)]
        if not root_folders:
            return []

        # Collect folders grouped by the group_id stored in their marker
        group_id_folders: dict[str, list[str]] = {}
        dirs_scanned = 0
        markers_found = 0

        for root in root_folders:
            for dirpath, dirnames, _filenames in os.walk(root):
                dirs_scanned += 1
                marker_id = read_mirror_marker(dirpath)
                if marker_id is not None:
                    markers_found += 1
                    group_id_folders.setdefault(marker_id, []).append(dirpath)
                if dirs_scanned % 50 == 0 and progress_callback is not None:
                    progress_callback(dirs_scanned, markers_found)

        if progress_callback is not None:
            progress_callback(dirs_scanned, markers_found)

        # Also check each root folder itself (os.walk yields it as the
        # first dirpath, so this is already covered above, but be safe)

        # Existing folder sets -- skip already-registered groups
        existing_sets: list[set[str]] = []
        for group in self._groups.values():
            norm = {os.path.normpath(os.path.abspath(f)) for f in group.folders}
            existing_sets.append(norm)

        new_groups: list[MirrorGroup] = []
        for gid, folders in group_id_folders.items():
            if len(folders) < 2:
                continue
            folder_set = set(folders)
            if folder_set in existing_sets:
                continue
            group = self.create_group(folders=folders)
            new_groups.append(group)

        return new_groups

    def scan_content_mirrors(
        self,
        root_folders: list[str],
        progress_callback: Optional["Callable[[int, int], None]"] = None,
    ) -> tuple[list[list[str]], list[list[str]]]:
        """Scan folders for content-based mirrors.

        Recursively walks each root folder and all its subfolders.
        Computes a content fingerprint for each directory based on the
        SHA-256 hashes of all contained files (excluding the
        ``.hardlink_mirror`` marker), structured by directory hierarchy
        but ignoring file and folder names.

        Returns:
            A pair ``(auto_confirmed, candidates)``.

            *auto_confirmed* – folder lists where **every** folder already
            carries a ``.hardlink_mirror`` marker (previously approved by
            the user).  The caller can create groups for these without
            asking.

            *candidates* – folder lists that need manual review.
        """
        import hashlib

        root_folders = [os.path.normpath(os.path.abspath(f))
                        for f in root_folders if os.path.isdir(f)]
        if not root_folders:
            return [], []

        fp_cache: dict[str, str | None] = {}
        _stats = {"dirs": 0, "files": 0}

        def _report():
            if progress_callback is not None:
                progress_callback(_stats["dirs"], _stats["files"])

        def _hash_file(filepath: str) -> str:
            h = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    h.update(chunk)
            _stats["files"] += 1
            if _stats["files"] % 50 == 0:
                _report()
            return h.hexdigest()

        def _dir_fingerprint(dirpath: str) -> str | None:
            dirpath = os.path.normpath(dirpath)
            if dirpath in fp_cache:
                return fp_cache[dirpath]

            try:
                entries = list(os.scandir(dirpath))
            except (OSError, PermissionError):
                fp_cache[dirpath] = None
                return None

            file_fps: list[str] = []
            child_fps: list[str] = []

            for entry in entries:
                try:
                    if entry.is_file(follow_symlinks=False):
                        # Skip the marker file so it never affects the fingerprint
                        if entry.name == MIRROR_MARKER:
                            continue
                        file_fps.append(_hash_file(entry.path))
                    elif entry.is_dir(follow_symlinks=False):
                        cfp = _dir_fingerprint(entry.path)
                        if cfp is not None:
                            child_fps.append(cfp)
                except (OSError, PermissionError):
                    continue

            if not file_fps and not child_fps:
                fp_cache[dirpath] = None
                return None

            file_fps.sort()
            child_fps.sort()

            combined = hashlib.sha256(
                (';'.join(file_fps) + '|' + ';'.join(child_fps)).encode()
            ).hexdigest()
            fp_cache[dirpath] = combined
            _stats["dirs"] += 1
            if _stats["dirs"] % 20 == 0:
                _report()
            return combined

        for root in root_folders:
            _dir_fingerprint(root)
        _report()

        # Group directories by fingerprint
        fp_groups: dict[str, list[str]] = {}
        for dirpath, fp in fp_cache.items():
            if fp is not None:
                fp_groups.setdefault(fp, []).append(dirpath)

        # Existing folder sets – skip already-registered groups
        existing_sets: list[set[str]] = []
        for group in self._groups.values():
            norm = {os.path.normpath(os.path.abspath(f)) for f in group.folders}
            existing_sets.append(norm)

        auto_confirmed: list[list[str]] = []
        candidates: list[list[str]] = []

        for folders in fp_groups.values():
            if len(folders) < 2:
                continue
            # Remove ancestor directories
            filtered = [
                f for f in folders
                if not any(
                    other != f and other.startswith(f + os.sep)
                    for other in folders
                )
            ]
            if len(filtered) < 2:
                continue
            if set(filtered) in existing_sets:
                continue
            # Separate: all marked → auto, otherwise → candidate
            if all(has_mirror_marker(f) for f in filtered):
                auto_confirmed.append(filtered)
            else:
                candidates.append(filtered)

        return auto_confirmed, candidates

    def scan_for_mirrors(self, folders: list[str]) -> list["MirrorGroup"]:
        """Scan folders and discover mirror groups from shared hardlinks.

        Walks each folder recursively, collecting files by (dev, inode).
        Two folders that share at least one hardlinked file are considered
        mirrors of each other.  Connected components of the "shares a
        hardlink" relation form mirror groups.

        Groups that already exist in the registry (same set of folders)
        are skipped.  Newly discovered groups are added to the registry.

        Returns:
            List of newly created MirrorGroup objects.
        """
        folders = [os.path.normpath(os.path.abspath(f))
                   for f in folders if os.path.isdir(f)]
        if len(folders) < 2:
            return []

        # Map (dev, inode) -> set of folder indices that contain the file
        inode_to_folders: dict[tuple[int, int], set[int]] = {}

        for idx, folder in enumerate(folders):
            for dirpath, _dirnames, filenames in os.walk(folder):
                for fname in filenames:
                    full_path = os.path.join(dirpath, fname)
                    try:
                        st = os.stat(full_path)
                        key = (st.st_dev, st.st_ino)
                        if key not in inode_to_folders:
                            inode_to_folders[key] = set()
                        inode_to_folders[key].add(idx)
                    except OSError:
                        continue

        # Build adjacency: which folders share at least one hardlink?
        # Use union-find to group connected folders.
        parent = list(range(len(folders)))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for folder_indices in inode_to_folders.values():
            if len(folder_indices) < 2:
                continue
            indices = list(folder_indices)
            for i in range(1, len(indices)):
                union(indices[0], indices[i])

        # Collect groups (only those with 2+ folders)
        components: dict[int, list[str]] = {}
        for idx in range(len(folders)):
            root = find(idx)
            if root not in components:
                components[root] = []
            components[root].append(folders[idx])

        # Determine existing folder sets to avoid duplicates
        existing_sets: list[set[str]] = []
        for group in self._groups.values():
            norm = {os.path.normpath(os.path.abspath(f)) for f in group.folders}
            existing_sets.append(norm)

        new_groups = []
        for component_folders in components.values():
            if len(component_folders) < 2:
                continue
            folder_set = set(component_folders)
            # Skip if already registered
            if folder_set in existing_sets:
                continue
            group = self.create_group(folders=component_folders)
            new_groups.append(group)

        return new_groups
