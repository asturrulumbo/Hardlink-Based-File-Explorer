# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Hardlink Manager.

Build with:
    pyinstaller hardlink_manager.spec

Or use the build script:
    python build.py
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["hardlink_manager/main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "hardlink_manager",
        "hardlink_manager.core",
        "hardlink_manager.core.hardlink_ops",
        "hardlink_manager.core.search",
        "hardlink_manager.ui",
        "hardlink_manager.ui.app",
        "hardlink_manager.ui.dialogs",
        "hardlink_manager.ui.file_browser",
        "hardlink_manager.ui.search_panel",
        "hardlink_manager.utils",
        "hardlink_manager.utils.filesystem",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "test", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="HardlinkManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window — GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
