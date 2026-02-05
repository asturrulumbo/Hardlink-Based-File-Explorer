"""Filesystem utility functions for cross-platform hardlink support."""

import os
import platform
import stat


def get_inode(path: str) -> int:
    """Get the inode (file index number) for a file.

    On Windows, this uses the file index number from the Win32 API.
    On Unix/Linux, this uses the standard inode from os.stat().
    """
    st = os.stat(path)
    return st.st_ino


def get_hardlink_count(path: str) -> int:
    """Get the number of hardlinks pointing to the same file data."""
    st = os.stat(path)
    return st.st_nlink


def get_file_size(path: str) -> int:
    """Get file size in bytes."""
    return os.path.getsize(path)


def format_file_size(size_bytes: int) -> str:
    """Format a file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def is_same_volume(path1: str, path2: str) -> bool:
    """Check if two paths are on the same filesystem/volume.

    Hardlinks can only be created within the same volume.
    """
    if platform.system() == "Windows":
        # On Windows, compare drive letters
        drive1 = os.path.splitdrive(os.path.abspath(path1))[0].upper()
        drive2 = os.path.splitdrive(os.path.abspath(path2))[0].upper()
        return drive1 == drive2
    else:
        # On Unix/Linux, compare device IDs
        stat1 = os.stat(os.path.dirname(os.path.abspath(path1))
                        if not os.path.exists(path1)
                        else os.path.abspath(path1))
        stat2 = os.stat(os.path.dirname(os.path.abspath(path2))
                        if not os.path.exists(path2)
                        else os.path.abspath(path2))
        return stat1.st_dev == stat2.st_dev


def is_regular_file(path: str) -> bool:
    """Check if a path points to a regular file (not a directory/symlink)."""
    return os.path.isfile(path) and not os.path.islink(path)


def open_file(path: str) -> None:
    """Open a file with the system's default application."""
    import subprocess

    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
