param(
  [string]$RepoId = "Systran/faster-whisper-medium",
  [string]$OutDir = "$env:LOCALAPPDATA\TranscribatorAud\models\Systran__faster-whisper-medium"
)

$env:HUGGINGFACE_HUB_CACHE = "$env:LOCALAPPDATA\TranscribatorAud\hf_cache"
$env:HF_HUB_ENABLE_HF_TRANSFER = "1"

Write-Host "Downloading $RepoId -> $OutDir"
python - <<'PY'
from pathlib import Path
from app.core.model_prefetch import prefetch_model

repo = r"$RepoId"
out_dir = Path(r"$OutDir")
print(prefetch_model(repo, out_dir))
PY
