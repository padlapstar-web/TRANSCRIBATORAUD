import json
import os
import logging
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple

from huggingface_hub import hf_hub_download, snapshot_download

log = logging.getLogger(__name__)

FILES = ["model.bin", "tokenizer.json", "config.json", "README.md"]
_MODEL_BIN_PATTERN = "model.bin*"
_REQUIRED_JSON = ("config.json", "tokenizer.json")


def _status_callback(cb: Optional[Callable[[str], None]], message: str) -> None:
    if cb is None:
        log.info(message)
        return
    try:
        cb(message)
    except Exception:
        log.exception("status callback failed")
    log.info(message)


def _load_json(path: Path) -> Tuple[bool, Optional[str]]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return False, "not a JSON object"
        if path.name == "tokenizer.json" and "model" not in data:
            return False, "tokenizer.json missing 'model' key"
        return True, None
    except Exception as exc:  # pragma: no cover - diagnostics only
        return False, str(exc)


def validate_snapshot(path: Path) -> Tuple[bool, Dict[str, str]]:
    """Validate the local model snapshot and return issues if any."""

    issues: Dict[str, str] = {}

    if not path.exists() or not path.is_dir():
        issues[path.as_posix()] = "not a directory"
        return False, issues

    model_bins = [candidate for candidate in path.glob(_MODEL_BIN_PATTERN) if candidate.is_file()]
    if not model_bins:
        issues[_MODEL_BIN_PATTERN] = "missing"
    else:
        for candidate in model_bins:
            if candidate.stat().st_size == 0:
                issues[candidate.name] = "empty"

    for name in _REQUIRED_JSON:
        candidate = path / name
        if not candidate.exists() or candidate.stat().st_size == 0:
            issues[name] = "missing"
            continue
        ok, reason = _load_json(candidate)
        if not ok:
            issues[name] = f"invalid JSON ({reason})" if reason else "invalid JSON"

    return (not issues), issues


def _remove_patterns(base: Path, patterns: Sequence[str]) -> None:
    for pattern in patterns:
        for candidate in base.glob(pattern):
            try:
                candidate.unlink()
            except FileNotFoundError:
                continue
            except IsADirectoryError:
                # When pattern accidentally matches a directory (unlikely) remove recursively
                for nested in candidate.rglob("*"):
                    try:
                        nested.unlink()
                    except Exception:
                        pass
                try:
                    candidate.rmdir()
                except Exception:
                    pass


def _redownload_problem_files(
    repo_id: str,
    local_dir: Path,
    issues: Dict[str, str],
    status_cb: Optional[Callable[[str], None]],
) -> None:
    problematic = sorted(issues.keys())
    bins_required = any(name.startswith("model.bin") for name in problematic) or _MODEL_BIN_PATTERN in problematic

    if bins_required:
        _status_callback(status_cb, "Повторная загрузка бинарных файлов модели…")
        _remove_patterns(local_dir, [_MODEL_BIN_PATTERN])
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            allow_patterns=["model.bin", "model.bin.*"],
            resume_download=True,
            max_workers=4,
            tqdm_class=None,
        )

    for name in problematic:
        if name.startswith("model.bin") or name == _MODEL_BIN_PATTERN:
            continue  # already handled via snapshot_download above
        _status_callback(status_cb, f"Перекачиваем {name}… ({issues[name]})")
        target = local_dir / name
        if target.exists():
            try:
                target.unlink()
            except Exception:
                pass
        hf_hub_download(
            repo_id=repo_id,
            filename=name,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )


def ensure_model(
    repo_id: str,
    local_dir: str,
    on_status: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
    force_files: Optional[Sequence[str]] = None,
) -> str:
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
    os.environ.setdefault("HF_HUB_ENABLE_XET", "1")

    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)

    if force_files:
        _status_callback(on_status, "Повторная загрузка выбранных файлов модели…")
        _remove_patterns(local_path, force_files)

    if on_progress:
        try:
            on_progress(0, 1)
        except Exception:
            log.exception("progress callback failed")

    _status_callback(on_status, "Подключение к Hugging Face…")

    snapshot_download(
        repo_id=repo_id,
        local_dir=str(local_path),
        local_dir_use_symlinks=False,
        allow_patterns=FILES,
        resume_download=True,
        max_workers=4,
        tqdm_class=None,
    )

    attempts = 0
    while True:
        ok, issues = validate_snapshot(local_path)
        if ok:
            break
        attempts += 1
        if attempts > 2:
            details = ", ".join(f"{name}: {reason}" for name, reason in issues.items())
            raise RuntimeError(f"Не удалось восстановить модель {repo_id}: {details}")
        _redownload_problem_files(repo_id, local_path, issues, on_status)

    if on_progress:
        try:
            on_progress(1, 1)
        except Exception:
            log.exception("progress callback failed")

    return str(local_path)


__all__ = ["ensure_model", "validate_snapshot"]
