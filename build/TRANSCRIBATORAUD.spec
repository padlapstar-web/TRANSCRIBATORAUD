# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(os.environ.get("PYI_SPEC_DIR", "")) if os.environ.get("PYI_SPEC_DIR") else None
if not SPEC_DIR:
    try:
        SPEC_DIR = Path(__file__).resolve().parent
    except NameError:
        if (Path.cwd() / "build" / "TRANSCRIBATORAUD.spec").exists():
            SPEC_DIR = Path.cwd() / "build"
        else:
            SPEC_DIR = Path.cwd()

if SPEC_DIR.name.lower() == "build":
    default_project_root = SPEC_DIR.parent
else:
    default_project_root = SPEC_DIR

PROJECT_ROOT = Path(os.environ.get("PYI_PROJECT_ROOT", default_project_root))

pathex = [str(PROJECT_ROOT), str(SPEC_DIR)]

app_entry = PROJECT_ROOT / "app" / "main.py"

hiddenimports = collect_submodules("app")

a = Analysis(
    [str(app_entry)],
    pathex=pathex,
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=a.cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TRANSCRIBATORAUD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TRANSCRIBATORAUD",
)
