# -*- mode: python ; coding: utf-8 -*-
import pathlib
from PyInstaller.utils.hooks import collect_submodules

project_root = pathlib.Path(__file__).resolve().parents[1]
app_entry = project_root / "app" / "main.py"

hiddenimports = collect_submodules("app")

a = Analysis(
    [str(app_entry)],
    pathex=[str(project_root / "app")],
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
