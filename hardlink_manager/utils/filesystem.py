"""Filesystem utility functions for cross-platform hardlink support."""

import os
import platform
import stat
import unicodedata


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


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in Windows/NTFS filenames.

    Strips invisible Unicode control and formatting characters (e.g. RTL marks,
    zero-width joiners) that tkinter input widgets may inject, as well as the
    standard Windows-forbidden characters.
    """
    # Strip Unicode control (Cc) and formatting (Cf) characters —
    # includes bidi marks (U+200E/F, U+202A-E), BOM (U+FEFF), ZWJ/ZWNJ, etc.
    cleaned = "".join(
        ch for ch in name
        if unicodedata.category(ch) not in ("Cc", "Cf")
    )
    # Remove characters forbidden in Windows filenames
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(ch for ch in cleaned if ch not in forbidden)
    # Windows doesn't allow trailing dots or spaces in names
    cleaned = cleaned.strip().rstrip(".")
    return cleaned


def is_regular_file(path: str) -> bool:
    """Check if a path points to a regular file (not a directory/symlink)."""
    return os.path.isfile(path) and not os.path.islink(path)


def is_symlink(path: str) -> bool:
    """Check if a path is a symlink."""
    return os.path.islink(path)


def create_symlink(target: str, link_path: str) -> str:
    """Create a symbolic link pointing to target.

    Always creates a directory symlink (target_is_directory=True) since this
    application only supports folder symlinks.

    Args:
        target: The absolute path the symlink will point to.
        link_path: Where the symlink will be created.

    Returns:
        The created symlink path.

    Raises:
        FileNotFoundError: If target does not exist.
        FileExistsError: If link_path already exists.
        OSError: If symlink creation fails (e.g. insufficient privileges on Windows).
    """
    target = os.path.abspath(target)
    link_path = os.path.abspath(link_path)

    if not os.path.exists(target):
        raise FileNotFoundError(f"Symlink target not found: {target}")

    if not os.path.isdir(target):
        raise ValueError(f"Symlink target must be a directory: {target}")

    if os.path.exists(link_path) or os.path.islink(link_path):
        raise FileExistsError(f"Path already exists: {link_path}")

    os.symlink(target, link_path, target_is_directory=True)
    return link_path


def read_symlink_target(path: str) -> str:
    """Read and return the absolute target of a symlink."""
    target = os.readlink(path)
    if not os.path.isabs(target):
        target = os.path.normpath(os.path.join(os.path.dirname(path), target))
    return target


def is_symlink_broken(path: str) -> bool:
    """Check if a symlink is dangling (target no longer exists)."""
    if not os.path.islink(path):
        return False
    return not os.path.exists(path)


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


def _popen_safe(args: list[str]) -> None:
    """Launch a subprocess safely, even in PyInstaller --noconsole mode."""
    import subprocess

    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if platform.system() == "Windows":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = si
    subprocess.Popen(args, **kwargs)


def reveal_in_explorer(path: str) -> None:
    """Open the containing folder in the system file manager and select the item."""
    import subprocess

    system = platform.system()
    abspath = os.path.abspath(path)

    if system == "Windows":
        if os.path.isdir(abspath):
            # Open the folder itself
            os.startfile(abspath)
        else:
            # Open Explorer with the file selected
            subprocess.Popen(["explorer", "/select,", abspath])
    elif system == "Darwin":
        _popen_safe(["open", "-R", abspath])
    else:
        # Linux: open the containing directory
        folder = abspath if os.path.isdir(abspath) else os.path.dirname(abspath)
        _popen_safe(["xdg-open", folder])


def copy_item(src: str, dest_dir: str, new_name: str = "") -> str:
    """Copy a file or folder to dest_dir. Returns the destination path."""
    import shutil

    name = new_name or os.path.basename(src)
    dest = os.path.join(dest_dir, name)
    if os.path.exists(dest):
        raise FileExistsError(f"'{name}' already exists in the destination.")
    if os.path.isdir(src):
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)
    return dest


def move_item(src: str, dest_dir: str, new_name: str = "") -> str:
    """Move a file or folder to dest_dir. Returns the destination path."""
    import shutil

    name = new_name or os.path.basename(src)
    dest = os.path.join(dest_dir, name)
    if os.path.exists(dest):
        raise FileExistsError(f"'{name}' already exists in the destination.")
    shutil.move(src, dest)
    return dest


def delete_item(path: str) -> None:
    """Delete a file or folder (recursively)."""
    import shutil

    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.unlink(path)
    else:
        raise FileNotFoundError(f"'{path}' does not exist.")
