# No Binaries Policy

To keep this repository clean and portable, we do **not** commit binary, media, archive, or model artefacts. Keep the git history text-only so that reviewers can easily audit changes and clones remain light-weight.

## Forbidden artefacts

The following must never be committed:

- Executables and native libraries (`*.exe`, `*.dll`, `*.so`, `*.dylib`, `*.lib`, etc.).
- Build outputs (`dist/`, `build/`, `__pycache__/`, `*.spec`, temporary logs, etc.).
- Media and assets (`*.wav`, `*.mp3`, `*.mp4`, `*.jpg`, `*.png`, etc.).
- Machine-learning payloads and archives (`*.onnx`, `*.pt`, `*.pth`, `*.safetensors`, `*.zip`, `*.tar.gz`, etc.).
- Any file larger than 2 MB without explicit approval.

If you discover such files in the working tree, delete them before committing. BinaryGuard in CI enforces this policy and will fail any push or pull request containing blocked artefacts.

## Working with large dependencies

When a tool or dependency requires binary assets (FFmpeg, ML models, etc.), download them at build-time instead of committing them. Use the scripts in `scripts/` (`fetch_assets.py`, `bootstrap`, `build_exe`) to automate setup, downloads with checksum verification, and packaging. Place downloaded artefacts in `resources/`, `data/`, or `models/` directories that are already ignored by `.gitignore`.

## Pull request expectations

Before submitting a PR, ensure:

1. `python tools/ci/check_no_binaries.py` passes locally.
2. `git status` is clean after running any build or bootstrap scripts.
3. All new files are text-based and under 2 MB.

If BinaryGuard fails in CI, remove the offending files and push a fixed commit. The policy is strict by design.
