# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

PROJECT_ROOT = Path.cwd()
ENTRY_SCRIPT = PROJECT_ROOT / "app" / "main.py"
if not ENTRY_SCRIPT.exists():
    raise FileNotFoundError(f"Entry script not found: {ENTRY_SCRIPT}")

datas = [
    (str(PROJECT_ROOT / "resources" / "ffmpeg" / "ffmpeg.exe"), "resources/ffmpeg"),
    (str(PROJECT_ROOT / "resources" / "ffmpeg" / "ffprobe.exe"), "resources/ffmpeg"),
]
datas += collect_data_files("PySide6")

hiddenimports = []
for module in ("ct2", "faster_whisper", "xml.parsers"):
    try:
        hiddenimports += list(collect_submodules(module))
    except Exception:
        pass
hiddenimports += ["pkg_resources", "importlib_metadata"]

binaries = []


a = Analysis(
    [str(ENTRY_SCRIPT)],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="TRANSCRIBATORAUD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TRANSCRIBATORAUD",
)
