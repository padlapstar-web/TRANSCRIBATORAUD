#!/usr/bin/env python3
import os, sys, subprocess, pathlib, mimetypes

BAD_EXT = {
  '.exe','.dll','.so','.dylib','.a','.lib','.pyd','.o','.obj',
  '.bin','.dat','.pack','.zip','.7z','.rar','.tar','.gz','.xz',
  '.mp3','.wav','.flac','.aac','.m4a','.ogg',
  '.mp4','.mkv','.mov','.avi',
  '.jpg','.jpeg','.png','.gif','.bmp','.tiff','.webp',
  '.pdf','.psd','.ai','.sketch','.ico',
  '.safetensors','.pth','.pt','.onnx'
}
MAX_BYTES = 2_000_000  # 2MB

def git_files():
    out = subprocess.check_output(['git','ls-files','-z'])
    return [p for p in out.decode('utf-8').split('\x00') if p]

def is_text(p):
    try:
        with open(p,'rb') as f:
            chunk = f.read(8000)
        if b'\x00' in chunk:
            return False
        try:
            chunk.decode('utf-8')
            return True
        except UnicodeDecodeError:
            pass
        typ = mimetypes.guess_type(p)[0] or ''
        return 'text' in typ or typ in ('application/json','application/xml','application/x-sh')
    except Exception:
        return False

bad = []
for p in git_files():
    ext = pathlib.Path(p).suffix.lower()
    if ext in BAD_EXT: bad.append((p,'bad-ext'))
    elif os.path.getsize(p) > MAX_BYTES: bad.append((p,'too-large'))
    elif not is_text(p): bad.append((p,'non-text'))

if bad:
    for p,why in bad: print(f'ERROR: {p} -> {why}')
    print(f'Found {len(bad)} non-allowed artifacts. Remove them or add to build artifacts outside git.')
    sys.exit(1)
print('OK: no binaries detected.')
