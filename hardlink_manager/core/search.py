"""Intersection search: find files appearing in multiple specified folders."""

import os
from dataclasses import dataclass, field
from typing import Optional

from hardlink_manager.utils.filesystem import get_inode


@dataclass
class SearchResult:
    """A file found in the intersection of multiple folders."""
    inode: int
    filename: str
    paths: list[str] = field(default_factory=list)
    size: int = 0


def intersection_search(
    folders: list[str],
    filename_pattern: Optional[str] = None,
) -> list[SearchResult]:
    """Find files that appear in ALL specified folders (via hardlink/inode matching).

    Args:
        folders: List of 2+ directory paths to intersect.
        filename_pattern: Optional substring filter for filenames (case-insensitive).

    Returns:
        List of SearchResult objects for files found in all specified folders.

    Raises:
        ValueError: If fewer than 2 folders are specified.
    """
    if len(folders) < 2:
        raise ValueError("Intersection search requires at least 2 folders.")

    # Build a mapping: inode -> {folder_index: [paths_in_that_folder]}
    # We use (device, inode) as the key for correctness
    inode_map: dict[tuple[int, int], dict[int, list[str]]] = {}

    for folder_idx, folder in enumerate(folders):
        folder = os.path.abspath(folder)
        if not os.path.isdir(folder):
            continue
        for entry in os.scandir(folder):
            if not entry.is_file(follow_symlinks=False):
                continue
            if filename_pattern and filename_pattern.lower() not in entry.name.lower():
                continue
            try:
                # Use os.stat() instead of entry.stat() because
                # DirEntry.stat() on Windows doesn't populate st_ino
                st = os.stat(entry.path)
                key = (st.st_dev, st.st_ino)
                if key not in inode_map:
                    inode_map[key] = {}
                if folder_idx not in inode_map[key]:
                    inode_map[key][folder_idx] = []
                inode_map[key][folder_idx].append(entry.path)
            except OSError:
                continue

    # Filter to files present in ALL folders
    num_folders = len(folders)
    results = []
    for (dev, inode), folder_entries in inode_map.items():
        if len(folder_entries) >= num_folders:
            all_paths = []
            for paths in folder_entries.values():
                all_paths.extend(paths)
            # Use the first path for metadata
            first_path = all_paths[0]
            try:
                size = os.path.getsize(first_path)
            except OSError:
                size = 0
            results.append(SearchResult(
                inode=inode,
                filename=os.path.basename(first_path),
                paths=sorted(all_paths),
                size=size,
            ))

    results.sort(key=lambda r: r.filename.lower())
    return results
