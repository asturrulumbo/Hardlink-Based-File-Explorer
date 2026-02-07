"""Mirror group registry: data model and JSON persistence."""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


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


class MirrorGroupRegistry:
    """Persistent registry of mirror groups, backed by a JSON file."""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            # Default: store next to the executable / in app directory
            app_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(app_dir, "..", DEFAULT_REGISTRY_FILENAME)
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
            group.folders = folders
            # Auto-update name from folder names
            group.name = group.auto_name()
        if sync_enabled is not None:
            group.sync_enabled = sync_enabled
        group.touch()
        self.save()
        return group

    def delete_group(self, group_id: str) -> bool:
        """Delete a mirror group and save. Returns True if it existed."""
        if group_id in self._groups:
            del self._groups[group_id]
            self.save()
            return True
        return False

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
