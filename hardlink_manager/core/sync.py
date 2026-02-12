"""Sync operations for mirror groups: propagate files and folder symlinks."""

import os
from typing import Optional

from hardlink_manager.core.hardlink_ops import create_hardlink, create_folder_symlink
from hardlink_manager.core.mirror_groups import MIRROR_MARKER, MirrorGroup
from hardlink_manager.utils.filesystem import (
    create_symlink,
    get_inode,
    is_symlink,
    read_symlink_target,
)


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


def sync_symlink_to_group(symlink_path: str, group: MirrorGroup) -> list[str]:
    """Replicate a folder symlink to all other folders in the mirror group.

    The symlink is treated as an opaque entry: only the symlink itself is
    replicated (pointing to the same absolute target), its contents are never
    traversed or synced.

    Args:
        symlink_path: Path to the symlink that was created.
        group: The mirror group to sync across.

    Returns:
        List of paths where new symlinks were created.
    """
    symlink_path = os.path.normpath(os.path.abspath(symlink_path))
    source_root = _find_root_folder(symlink_path, group)
    if source_root is None:
        return []

    if not os.path.islink(symlink_path):
        return []

    target = read_symlink_target(symlink_path)
    rel_path = os.path.relpath(symlink_path, source_root)

    created = []
    for folder in group.folders:
        folder = os.path.normpath(os.path.abspath(folder))
        if folder == source_root:
            continue

        dest_path = os.path.join(folder, rel_path)

        # Already exists — check if it's a symlink to the same target
        if os.path.islink(dest_path):
            existing_target = read_symlink_target(dest_path)
            if os.path.normpath(existing_target) == os.path.normpath(target):
                continue  # Already correct
            continue  # Different symlink, don't overwrite
        if os.path.exists(dest_path):
            continue  # Regular file/dir with same name, skip

        dest_dir = os.path.dirname(dest_path)
        os.makedirs(dest_dir, exist_ok=True)

        try:
            create_symlink(target, dest_path)
            created.append(dest_path)
        except (OSError, FileExistsError):
            continue

    return created


def delete_symlink_from_group(symlink_path: str, group: MirrorGroup) -> list[str]:
    """Delete a folder symlink from ALL folders in a mirror group.

    Matches symlinks at the same relative path that point to the same target.

    Args:
        symlink_path: Path to the symlink being deleted.
        group: The mirror group.

    Returns:
        List of paths that were deleted.
    """
    symlink_path = os.path.normpath(os.path.abspath(symlink_path))
    root_folder = _find_root_folder(symlink_path, group)
    if root_folder is None:
        return []

    if not os.path.islink(symlink_path):
        return []

    target = read_symlink_target(symlink_path)
    rel_path = os.path.relpath(symlink_path, root_folder)

    deleted = []
    for folder in group.folders:
        folder = os.path.normpath(os.path.abspath(folder))
        candidate = os.path.join(folder, rel_path)
        if not os.path.islink(candidate):
            continue
        try:
            candidate_target = read_symlink_target(candidate)
            if os.path.normpath(candidate_target) == os.path.normpath(target):
                os.unlink(candidate)
                deleted.append(candidate)
        except OSError:
            continue

    return deleted


def sync_group(group: MirrorGroup) -> dict[str, list[str]]:
    """Full recursive sync of a mirror group.

    Walks all folders recursively, collecting unique files by (dev, inode).
    Then ensures every file exists at the same relative path in every folder
    via hardlinks, creating subdirectories as needed.

    Returns:
        Dict mapping each created hardlink path to its source path.
    """
    if len(group.folders) < 2:
        return {}

    # Collect all unique files by (dev, inode) -> (source_path, relative_path)
    unique_files: dict[tuple[int, int], tuple[str, str]] = {}
    # Collect symlinks by (relative_path, target) -> source symlink path
    unique_symlinks: dict[tuple[str, str], str] = {}

    for folder in group.folders:
        folder = os.path.normpath(os.path.abspath(folder))
        if not os.path.isdir(folder):
            continue
        for dirpath, dirnames, filenames in os.walk(folder):
            # Detect folder symlinks among directory entries (os.walk
            # yields them in dirnames but does not follow them by default).
            symlink_dirs = []
            for dname in dirnames:
                dpath = os.path.join(dirpath, dname)
                if os.path.islink(dpath):
                    symlink_dirs.append(dname)
                    try:
                        target = read_symlink_target(dpath)
                        rel = os.path.relpath(dpath, folder)
                        key = (rel, os.path.normpath(target))
                        if key not in unique_symlinks:
                            unique_symlinks[key] = dpath
                    except OSError:
                        continue
            # Remove symlink dirs so os.walk does not descend into them
            for sd in symlink_dirs:
                dirnames.remove(sd)

            for fname in filenames:
                if fname == MIRROR_MARKER:
                    continue
                full_path = os.path.join(dirpath, fname)
                try:
                    # Use os.stat() — DirEntry.stat() on Windows doesn't
                    # populate st_ino
                    st = os.stat(full_path)
                    key = (st.st_dev, st.st_ino)
                    if key not in unique_files:
                        rel = os.path.relpath(full_path, folder)
                        unique_files[key] = (full_path, rel)
                except OSError:
                    continue

    # For each unique file, ensure it exists at the same relative path in all folders
    created: dict[str, str] = {}
    for (dev, inode), (source_path, rel_path) in unique_files.items():
        for folder in group.folders:
            folder = os.path.normpath(os.path.abspath(folder))
            dest_path = os.path.join(folder, rel_path)

            if os.path.exists(dest_path):
                try:
                    st = os.stat(dest_path)
                    if st.st_ino == inode and st.st_dev == dev:
                        continue  # Already linked
                except OSError:
                    pass
                continue  # Different file with same name, skip

            dest_dir = os.path.dirname(dest_path)
            os.makedirs(dest_dir, exist_ok=True)
            try:
                create_hardlink(source_path, dest_dir, os.path.basename(rel_path))
                created[dest_path] = source_path
            except (OSError, ValueError, FileExistsError):
                continue

    # For each unique symlink, ensure it exists at the same relative path in all folders
    for (rel_path, norm_target), source_symlink in unique_symlinks.items():
        for folder in group.folders:
            folder = os.path.normpath(os.path.abspath(folder))
            dest_path = os.path.join(folder, rel_path)

            if os.path.islink(dest_path):
                existing = read_symlink_target(dest_path)
                if os.path.normpath(existing) == norm_target:
                    continue  # Already correct
                continue  # Different symlink, skip
            if os.path.exists(dest_path):
                continue  # Name taken by a regular entry, skip

            dest_dir = os.path.dirname(dest_path)
            os.makedirs(dest_dir, exist_ok=True)
            try:
                create_symlink(norm_target, dest_path)
                created[dest_path] = source_symlink
            except (OSError, FileExistsError):
                continue

    return created


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
