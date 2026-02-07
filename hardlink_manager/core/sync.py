"""Sync operations for mirror groups: propagate files across group folders."""

import os
from typing import Optional

from hardlink_manager.core.hardlink_ops import create_hardlink
from hardlink_manager.core.mirror_groups import MirrorGroup
from hardlink_manager.utils.filesystem import get_inode


def sync_file_to_group(source_path: str, group: MirrorGroup) -> list[str]:
    """Create hardlinks for a file in all other folders of the mirror group.

    Args:
        source_path: Path to the file that was added.
        group: The mirror group to sync across.

    Returns:
        List of paths where new hardlinks were created.
    """
    source_path = os.path.abspath(source_path)
    source_dir = os.path.dirname(source_path)
    filename = os.path.basename(source_path)
    source_inode = get_inode(source_path)
    source_dev = os.stat(source_path).st_dev

    created = []
    for folder in group.folders:
        folder = os.path.abspath(folder)
        if os.path.normpath(folder) == os.path.normpath(source_dir):
            continue

        dest_path = os.path.join(folder, filename)

        # Already exists — check if same inode (already linked)
        if os.path.exists(dest_path):
            try:
                st = os.stat(dest_path)
                if st.st_ino == source_inode and st.st_dev == source_dev:
                    continue  # Already hardlinked
            except OSError:
                pass
            continue  # Different file with same name, skip

        # Create the destination directory if it doesn't exist
        os.makedirs(folder, exist_ok=True)

        try:
            create_hardlink(source_path, folder, filename)
            created.append(dest_path)
        except (OSError, ValueError, FileExistsError):
            continue

    return created


def sync_group(group: MirrorGroup) -> dict[str, list[str]]:
    """Full sync of a mirror group: ensure all folders have the same files.

    Collects all unique files (by inode) across all folders, then ensures
    every file exists in every folder via hardlinks.

    Returns:
        Dict mapping each created hardlink path to its source path.
    """
    if len(group.folders) < 2:
        return {}

    # Collect all unique files by (dev, inode) -> (source_path, filename)
    unique_files: dict[tuple[int, int], tuple[str, str]] = {}

    for folder in group.folders:
        folder = os.path.abspath(folder)
        if not os.path.isdir(folder):
            continue
        try:
            for entry in os.scandir(folder):
                if not entry.is_file(follow_symlinks=False):
                    continue
                try:
                    st = entry.stat()
                    key = (st.st_dev, st.st_ino)
                    if key not in unique_files:
                        unique_files[key] = (entry.path, entry.name)
                except OSError:
                    continue
        except OSError:
            continue

    # For each unique file, ensure it exists in all folders
    created = {}
    for (dev, inode), (source_path, filename) in unique_files.items():
        for folder in group.folders:
            folder = os.path.abspath(folder)
            dest_path = os.path.join(folder, filename)

            if os.path.exists(dest_path):
                try:
                    st = os.stat(dest_path)
                    if st.st_ino == inode and st.st_dev == dev:
                        continue  # Already linked
                except OSError:
                    pass
                continue  # Different file with same name, skip

            os.makedirs(folder, exist_ok=True)
            try:
                create_hardlink(source_path, folder, filename)
                created[dest_path] = source_path
            except (OSError, ValueError, FileExistsError):
                continue

    return created


def delete_from_group(file_path: str, group: MirrorGroup) -> list[str]:
    """Delete a file from ALL folders in a mirror group.

    Finds all hardlinks to the file within the group's folders and removes them.

    Args:
        file_path: Path to the file being deleted.
        group: The mirror group.

    Returns:
        List of paths that were deleted.
    """
    file_path = os.path.abspath(file_path)
    try:
        target_inode = get_inode(file_path)
        target_dev = os.stat(file_path).st_dev
    except OSError:
        return []

    filename = os.path.basename(file_path)
    deleted = []

    for folder in group.folders:
        folder = os.path.abspath(folder)
        candidate = os.path.join(folder, filename)
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
