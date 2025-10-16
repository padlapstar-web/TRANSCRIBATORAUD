# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = collect_data_files("PySide6")
hiddenimports = []
try:
    hiddenimports += collect_submodules("ct2")
except Exception:
    pass
hiddenimports += collect_submodules("faster_whisper")
hiddenimports += [
    "xml.parsers.expat",
    "pkg_resources",
    "importlib_metadata",
]


a = Analysis(
    ["app/main.py"],
    pathex=[],
    binaries=[
        ("resources/ffmpeg/ffmpeg.exe", "resources/ffmpeg"),
        ("resources/ffmpeg/ffprobe.exe", "resources/ffmpeg"),
    ],
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
