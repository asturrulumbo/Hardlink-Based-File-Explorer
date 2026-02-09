"""Sync operations for mirror groups: propagate files across group folders."""

import os
from dataclasses import dataclass, field
from typing import Optional

from hardlink_manager.core.hardlink_ops import create_hardlink
from hardlink_manager.core.mirror_groups import (
    MIRROR_MARKER, MirrorGroup,
    load_sync_manifest, save_sync_manifest,
)
from hardlink_manager.utils.filesystem import get_inode


@dataclass
class SyncResult:
    """Detailed result of a sync_group operation."""
    created: dict[str, str] = field(default_factory=dict)   # dest -> source
    deleted: list[str] = field(default_factory=list)         # paths removed


def _find_root_folder(file_path: str, group: MirrorGroup) -> Optional[str]:
    """Return which of the group's folders contains file_path (or a parent of it)."""
    file_path = os.path.normpath(os.path.abspath(file_path))
    for folder in group.folders:
        norm = os.path.normpath(os.path.abspath(folder))
        if file_path == norm or file_path.startswith(norm + os.sep):
            return norm
    return None


def sync_file_to_group(source_path: str, group: MirrorGroup) -> list[str]:
    """Create hardlinks for a file in all other folders of the mirror group.

    Handles files in subdirectories by computing the relative path from the
    group root folder and replicating the same relative structure in every
    other group folder.

    Args:
        source_path: Path to the file that was added.
        group: The mirror group to sync across.

    Returns:
        List of paths where new hardlinks were created.
    """
    source_path = os.path.normpath(os.path.abspath(source_path))
    if os.path.basename(source_path) == MIRROR_MARKER:
        return []
    source_root = _find_root_folder(source_path, group)
    if source_root is None:
        return []

    rel_path = os.path.relpath(source_path, source_root)
    source_inode = get_inode(source_path)
    source_dev = os.stat(source_path).st_dev

    created = []
    for folder in group.folders:
        folder = os.path.normpath(os.path.abspath(folder))
        if folder == source_root:
            continue

        dest_path = os.path.join(folder, rel_path)
        dest_dir = os.path.dirname(dest_path)
        filename = os.path.basename(dest_path)

        # Already exists — check if same inode (already linked)
        if os.path.exists(dest_path):
            try:
                st = os.stat(dest_path)
                if st.st_ino == source_inode and st.st_dev == source_dev:
                    continue  # Already hardlinked
            except OSError:
                pass
            continue  # Different file with same name, skip

        # Create intermediate directories as needed
        os.makedirs(dest_dir, exist_ok=True)

        try:
            create_hardlink(source_path, dest_dir, filename)
            created.append(dest_path)
        except (OSError, ValueError, FileExistsError):
            continue

    return created


def sync_group(group: MirrorGroup,
               registry_path: Optional[str] = None) -> SyncResult:
    """Full recursive sync of a mirror group with deletion detection.

    Uses a *sync manifest* (a record of previously-synced relative paths)
    to distinguish between "new file that should be copied" and "file that
    was deleted and should be removed everywhere".

    Logic:
        1. Load the manifest of relative paths from the last sync.
        2. Walk every folder and collect which relative paths exist where.
        3. For each relative path that is in the manifest but **missing from
           at least one folder**: the file was deleted → remove it from all
           folders and drop it from the manifest.
        4. For each relative path present in **some** folders but **not** in
           the manifest: the file is new → hardlink it into the missing
           folders and add it to the manifest.
        5. Save the updated manifest.

    Returns:
        A ``SyncResult`` with *created* (dest → source) and *deleted* lists.
    """
    result = SyncResult()

    if len(group.folders) < 2:
        return result

    # Normalise folders
    norm_folders = []
    for f in group.folders:
        nf = os.path.normpath(os.path.abspath(f))
        if os.path.isdir(nf):
            norm_folders.append(nf)
    if len(norm_folders) < 2:
        return result

    # Load manifest (set of relative paths synced last time)
    if registry_path is None:
        from hardlink_manager.core.mirror_groups import _default_registry_path
        registry_path = _default_registry_path()
    manifest = load_sync_manifest(registry_path, group.id)

    # ----- Phase 1: inventory each folder -----
    # folder -> {rel_path -> (full_path, dev, inode)}
    folder_contents: dict[str, dict[str, tuple[str, int, int]]] = {}
    for folder in norm_folders:
        contents: dict[str, tuple[str, int, int]] = {}
        for dirpath, _dirnames, filenames in os.walk(folder):
            for fname in filenames:
                if fname == MIRROR_MARKER:
                    continue
                full_path = os.path.join(dirpath, fname)
                try:
                    st = os.stat(full_path)
                    rel = os.path.relpath(full_path, folder)
                    contents[rel] = (full_path, st.st_dev, st.st_ino)
                except OSError:
                    continue
        folder_contents[folder] = contents

    # All relative paths across all folders
    all_rel_paths: set[str] = set()
    for contents in folder_contents.values():
        all_rel_paths.update(contents.keys())

    new_manifest: set[str] = set()

    # ----- Phase 2: detect deletions -----
    for rel_path in list(manifest):
        # Which folders still have this file?
        present_folders = [
            f for f in norm_folders if rel_path in folder_contents[f]
        ]
        if len(present_folders) == len(norm_folders):
            # File present everywhere – still synced, keep in manifest
            new_manifest.add(rel_path)
            continue
        if not present_folders:
            # File gone from ALL folders – nothing to delete, drop from manifest
            continue
        # File missing from at least one folder → propagate deletion
        for folder in present_folders:
            full_path = folder_contents[folder][rel_path][0]
            try:
                os.unlink(full_path)
                result.deleted.append(full_path)
            except OSError:
                pass
        # Don't add to new_manifest (it's deleted)

    # ----- Phase 3: add new files -----
    for rel_path in all_rel_paths:
        if rel_path in manifest:
            # Already handled in phase 2
            continue

        # Find which folders have this file
        present: list[tuple[str, str, int, int]] = []  # (folder, full, dev, ino)
        missing: list[str] = []
        for folder in norm_folders:
            if rel_path in folder_contents[folder]:
                fp, dev, ino = folder_contents[folder][rel_path]
                present.append((folder, fp, dev, ino))
            else:
                missing.append(folder)

        if not present:
            continue
        if not missing:
            # Exists in all folders already – just record in manifest
            new_manifest.add(rel_path)
            continue

        # Pick first present copy as source
        source_folder, source_path, source_dev, source_ino = present[0]

        for folder in missing:
            dest_path = os.path.join(folder, rel_path)
            dest_dir = os.path.dirname(dest_path)
            os.makedirs(dest_dir, exist_ok=True)
            try:
                create_hardlink(source_path, dest_dir, os.path.basename(rel_path))
                result.created[dest_path] = source_path
            except (OSError, ValueError, FileExistsError):
                continue

        new_manifest.add(rel_path)

    # ----- Phase 4: clean up empty directories left by deletions -----
    if result.deleted:
        for folder in norm_folders:
            _prune_empty_dirs(folder)

    # ----- Phase 5: save updated manifest -----
    save_sync_manifest(registry_path, group.id, new_manifest)

    return result


def _prune_empty_dirs(root: str) -> None:
    """Remove empty subdirectories under *root* (bottom-up)."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if dirpath == root:
            continue
        # Skip if directory still has files (other than marker)
        remaining = [f for f in filenames if f != MIRROR_MARKER]
        if remaining or dirnames:
            continue
        # Remove marker if it's the only file left
        marker = os.path.join(dirpath, MIRROR_MARKER)
        if os.path.isfile(marker):
            try:
                os.remove(marker)
            except OSError:
                pass
        try:
            os.rmdir(dirpath)
        except OSError:
            pass


def delete_from_group(file_path: str, group: MirrorGroup) -> list[str]:
    """Delete a file from ALL folders in a mirror group.

    Finds the file's relative path within its group folder, then deletes
    the matching file (by inode) at the same relative path in all group folders.

    Args:
        file_path: Path to the file being deleted.
        group: The mirror group.

    Returns:
        List of paths that were deleted.
    """
    file_path = os.path.normpath(os.path.abspath(file_path))
    root_folder = _find_root_folder(file_path, group)
    if root_folder is None:
        return []

    try:
        target_inode = get_inode(file_path)
        target_dev = os.stat(file_path).st_dev
    except OSError:
        return []

    rel_path = os.path.relpath(file_path, root_folder)
    deleted = []

    for folder in group.folders:
        folder = os.path.normpath(os.path.abspath(folder))
        candidate = os.path.join(folder, rel_path)
        if not os.path.exists(candidate):
            continue
        try:
            st = os.stat(candidate)
            if st.st_ino == target_inode and st.st_dev == target_dev:
                os.unlink(candidate)
                deleted.append(candidate)
        except OSError:
            continue

    return deleted
