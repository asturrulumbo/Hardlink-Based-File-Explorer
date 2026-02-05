"""Build script to create a standalone .exe using PyInstaller.

Usage:
    python build.py           Build the .exe (one-file bundle)
    python build.py --onedir  Build as a one-directory bundle (faster startup)
    python build.py --clean   Clean build artifacts before building

Requirements:
    pip install pyinstaller
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SPEC_FILE = ROOT / "hardlink_manager.spec"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"


def clean():
    """Remove previous build artifacts."""
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            print(f"Removing {d}")
            shutil.rmtree(d)


def build(onedir: bool = False):
    """Run PyInstaller to produce the executable."""
    # Ensure pyinstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    if onedir:
        # One-directory mode: faster startup, multiple files in dist/HardlinkManager/
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--name", "HardlinkManager",
            "--noconsole",
            "--noconfirm",
            "--clean",
            "--distpath", str(DIST_DIR),
            "--workpath", str(BUILD_DIR),
            str(ROOT / "hardlink_manager" / "main.py"),
        ]
    else:
        # One-file mode via the spec file
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath", str(DIST_DIR),
            "--workpath", str(BUILD_DIR),
            str(SPEC_FILE),
        ]

    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    # Report result
    if onedir:
        exe_path = DIST_DIR / "HardlinkManager" / "HardlinkManager.exe"
    else:
        exe_path = DIST_DIR / "HardlinkManager.exe"

    # On Linux the extension won't be .exe but the binary will still be there
    exe_no_ext = exe_path.with_suffix("")
    found = exe_path if exe_path.exists() else (exe_no_ext if exe_no_ext.exists() else None)

    if found:
        size_mb = found.stat().st_size / (1024 * 1024)
        print(f"\nBuild successful!")
        print(f"  Executable: {found}")
        print(f"  Size: {size_mb:.1f} MB")
    else:
        print(f"\nBuild completed. Check {DIST_DIR} for output.")


def main():
    parser = argparse.ArgumentParser(description="Build Hardlink Manager executable")
    parser.add_argument("--onedir", action="store_true", help="Build as one-directory bundle (faster startup)")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts before building")
    args = parser.parse_args()

    if args.clean:
        clean()

    build(onedir=args.onedir)


if __name__ == "__main__":
    main()
