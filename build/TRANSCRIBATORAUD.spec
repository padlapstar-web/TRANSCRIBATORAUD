# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hiddenimports = []
try:
    hiddenimports += collect_submodules("ct2")
except Exception:
    pass
hiddenimports += collect_submodules("faster_whisper")
hiddenimports += list(collect_submodules("xml.parsers"))
hiddenimports += [
    "pkg_resources",
    "importlib_metadata",
]

datas = [
    ("resources/ffmpeg/ffmpeg.exe", "resources/ffmpeg"),
    ("resources/ffmpeg/ffprobe.exe", "resources/ffmpeg"),
]
datas += collect_data_files("PySide6")


a = Analysis(
    ["app/main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    name="TRANSCRIBATORAUD",
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="TRANSCRIBATORAUD",
)
