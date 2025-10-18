# No binaries policy

This repository must stay free of compiled, media, archive, and other binary artifacts. Only human-readable sources, configuration, and documentation belong in Git history.

## Forbidden content

The following must **never** be committed:

- Executables and libraries (`*.exe`, `*.dll`, `*.so`, `*.dylib`, `*.pyd`, `*.lib`, `*.a`, `*.obj`, etc.).
- Packaged artifacts (`*.zip`, `*.7z`, `*.tar`, `*.gz`, `*.xz`, etc.).
- Media assets (`*.wav`, `*.mp3`, `*.ogg`, `*.mp4`, `*.mov`, `*.avi`, images, icons, PDFs, design sources).
- Machine learning weights or datasets (`*.onnx`, `*.pt`, `*.pth`, `*.safetensors`, etc.).
- Any single file larger than 2 MB.

## How to ship binaries

1. Keep Git history clean—commit only the source code required to reproduce deliverables.
2. Fetch heavyweight dependencies at build time using automation scripts (see `scripts/fetch_assets.py`).
3. Generated assets, downloaded tools, and build outputs live under ignored directories such as `dist/`, `resources/ffmpeg/`, `models/`, or `data/`.
4. Every pull request is validated by the Binary Guard workflow (`.github/workflows/binary-guard.yml`) which runs `python tools/ci/check_no_binaries.py`. The job fails if a forbidden artifact is detected.

If you need to distribute compiled binaries, publish them through releases or other artifact storage, never as part of the repository.
