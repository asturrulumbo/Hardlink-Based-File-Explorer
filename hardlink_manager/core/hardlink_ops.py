"""Core hardlink operations: create, delete, and view hardlinks."""

import os
from typing import Optional

from hardlink_manager.utils.filesystem import (
    get_inode,
    is_regular_file,
    is_same_volume,
)


def create_hardlink(source_path: str, dest_dir: str, dest_name: Optional[str] = None) -> str:
    """Create a hardlink to source_path in dest_dir.

    Args:
        source_path: Path to the existing file.
        dest_dir: Directory where the hardlink will be created.
        dest_name: Optional name for the hardlink. Defaults to the source filename.

    Returns:
        The full path of the created hardlink.

    Raises:
        FileNotFoundError: If source_path does not exist.
        NotADirectoryError: If dest_dir is not a directory.
        ValueError: If source is not a regular file or paths are on different volumes.
        FileExistsError: If a file with the target name already exists in dest_dir.
        OSError: If hardlink creation fails for other reasons.
    """
    source_path = os.path.abspath(source_path)
    dest_dir = os.path.abspath(dest_dir)

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    if not is_regular_file(source_path):
        raise ValueError(f"Source must be a regular file (not a directory or symlink): {source_path}")

    if not os.path.isdir(dest_dir):
        raise NotADirectoryError(f"Destination is not a directory: {dest_dir}")

    if not is_same_volume(source_path, dest_dir):
        raise ValueError(
            f"Source and destination must be on the same volume.\n"
            f"Source: {source_path}\nDestination: {dest_dir}"
        )

    if dest_name is None:
        dest_name = os.path.basename(source_path)

    dest_path = os.path.join(dest_dir, dest_name)

    if os.path.exists(dest_path):
        raise FileExistsError(f"File already exists at destination: {dest_path}")

    os.link(source_path, dest_path)
    return dest_path


def delete_hardlink(path: str) -> None:
    """Delete a hardlink (unlink a file path).

    This removes the specified path. If other hardlinks to the same inode
    exist, the underlying file data is preserved. If this is the last
    hardlink, the file data is deleted.

    Args:
        path: Path of the hardlink to remove.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If path is not a regular file.
        OSError: If deletion fails.
    """
    path = os.path.abspath(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    if not is_regular_file(path):
        raise ValueError(f"Path must be a regular file: {path}")

    os.unlink(path)


def find_all_hardlinks(file_path: str, search_dirs: list[str]) -> list[str]:
    """Find all hardlinks to the same file across the given directories.

    Searches the specified directories (recursively) for files that share
    the same inode as file_path.

    Args:
        file_path: Path to the file whose hardlinks we want to find.
        search_dirs: List of directory paths to search within.

    Returns:
        List of paths that are hardlinks to the same file data,
        including file_path itself if it's within a search directory.
    """
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    target_inode = get_inode(file_path)
    target_dev = os.stat(file_path).st_dev
    results = []

    for search_dir in search_dirs:
        search_dir = os.path.abspath(search_dir)
        if not os.path.isdir(search_dir):
            continue
        for dirpath, _dirnames, filenames in os.walk(search_dir):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                try:
                    st = os.stat(full_path)
                    if st.st_ino == target_inode and st.st_dev == target_dev:
                        results.append(full_path)
                except OSError:
                    continue

    # Deduplicate (in case search_dirs overlap)
    seen = set()
    unique = []
    for p in results:
        normed = os.path.normpath(p)
        if normed not in seen:
            seen.add(normed)
            unique.append(normed)

    return sorted(unique)
