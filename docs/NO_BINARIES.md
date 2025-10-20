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

When a tool or dependency requires binary assets (FFmpeg, ML models, etc.), install them locally and keep them outside of git. The application autodetects FFmpeg via environment variables (`FFMPEG_BIN`, `FFMPEG_HOME`), the system `PATH`, and bundled folders in the PyInstaller build. Use the helper CLI flag `TRANSCRIBATORAUD.exe --check-ffmpeg` (или `python app/cli.py --check-ffmpeg`) to verify availability. Packaging scripts (`build/RunMe.ps1`, `scripts/build_exe.ps1`) copy binaries from the local installation into `dist/` during the build, but the repository continues to track only the placeholder `resources/ffmpeg/.gitkeep`.

## Pull request expectations

Before submitting a PR, ensure:

1. `python tools/ci/check_no_binaries.py` passes locally.
2. `git status` is clean after running any build or bootstrap scripts.
3. All new files are text-based and under 2 MB.

If BinaryGuard fails in CI, remove the offending files and push a fixed commit. The policy is strict by design.
