# Binary, Archive, and Media Policy

To keep the repository light-weight, auditable, and portable, we **never commit** generated or pre-built binary artifacts. This includes, but is not limited to:

- Executables and libraries: `.exe`, `.dll`, `.pyd`, `.so`, `.dylib`, `.lib`, `.a`, `.obj`, `.pdb`
- Archives and installers: `.zip`, `.7z`, `.tar.gz`, `.tar`, `.rar`, `.msi`
- Media files: `.wav`, `.mp3`, `.ogg`, `.mp4`, `.mov`, `.gif`, images, fonts, etc.
- Machine learning assets: `.pt`, `.onnx`, `.safetensors`, `.bin`, or any weights/models
- Databases and other large data: `.db`, `.sqlite`, CSVs or JSON over 2 MB, cached assets, etc.
- **Any file larger than 2 MB**, regardless of its type

## Local generation & downloads

If the project depends on large assets (models, media, datasets, etc.), they must be fetched or generated locally. Add automation scripts under `scripts/`—for example `scripts/fetch_assets.py`, `scripts/bootstrap.sh`/`.ps1`, or other reproducible steps—that download the resources into ignored directories such as `data/`, `models/`, or `dist/`. These scripts should verify file integrity (size and checksum) and can be invoked as part of the one-command bootstrap/build process.

## BinaryGuard enforcement

A BinaryGuard check runs in CI to detect forbidden file types or large files in the repository. If BinaryGuard reports a violation, the commit or pull request will fail. Always ensure that new files comply with this policy before pushing. When in doubt, regenerate the asset locally or add it to `.gitignore` instead of committing it.
