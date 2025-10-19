import hashlib
import json
import os
import logging
import shutil
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Sequence, Tuple

from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from requests import HTTPError

log = logging.getLogger(__name__)

FILES = [
    "model.bin",
    "model.bin.*",
    "tokenizer.json",
    "config.json",
    "vocabulary.json",
    "vocabulary.txt",
    "README.md",
]
_MODEL_BIN_PATTERN = "model.bin*"
_REQUIRED_JSON = ("config.json", "tokenizer.json")
VOCABULARY_CANDIDATES: Tuple[str, ...] = ("vocabulary.json", "vocabulary.txt")
_REQUIRED_TOKENS = {
    "<|startoftranscript|>",
    "<|endoftext|>",
    "<|nospeech|>",
    "<|notimestamps|>",
}

_HF_API = HfApi()


def _status_callback(cb: Optional[Callable[[str], None]], message: str) -> None:
    if cb is None:
        log.info(message)
        return
    try:
        cb(message)
    except Exception:
        log.exception("status callback failed")
    log.info(message)


def _load_json(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # pragma: no cover - diagnostics only
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "not a JSON object"
    return data, None


def _validate_tokenizer(path: Path) -> Optional[str]:
    data, error = _load_json(path)
    if data is None:
        return f"invalid JSON ({error})" if error else "invalid JSON"
    model = data.get("model")
    if not isinstance(model, dict):
        return "tokenizer.json missing 'model' section"
    vocab = model.get("vocab")
    if not isinstance(vocab, dict):
        return "tokenizer.json missing vocab"
    missing_tokens = sorted(token for token in _REQUIRED_TOKENS if token not in vocab)
    if missing_tokens:
        return "missing tokens: " + ", ".join(missing_tokens)
    merges = model.get("merges")
    if not isinstance(merges, list) or not merges:
        return "tokenizer.json missing merges"
    return None


def _normalise_vocabulary_payload(tokenizer_data: dict) -> dict:
    model_section = tokenizer_data.get("model")
    if not isinstance(model_section, dict):
        raise ValueError("tokenizer.json missing 'model' section")
    vocab = model_section.get("vocab")
    if not isinstance(vocab, dict):
        raise ValueError("tokenizer.json missing vocab")
    merges = model_section.get("merges")
    if not isinstance(merges, list) or not merges:
        raise ValueError("tokenizer.json missing merges")
    payload = {
        "type": model_section.get("type", "BPE"),
        "model": {
            key: value
            for key, value in model_section.items()
            if key in {"vocab", "merges", "continuing_subword_prefix", "end_of_word_suffix", "unk_token"}
        },
    }
    payload["model"].setdefault("unk_token", "<unk>")
    payload["model"].setdefault("continuing_subword_prefix", "")
    payload["model"].setdefault("end_of_word_suffix", "")
    return payload


def _validate_vocabulary_json(path: Path) -> Optional[str]:
    data, error = _load_json(path)
    if data is None:
        return f"invalid JSON ({error})" if error else "invalid JSON"
    model_section = data.get("model")
    if not isinstance(model_section, dict):
        return "vocabulary.json missing model section"
    vocab = model_section.get("vocab") or model_section.get("vocabulary")
    if not isinstance(vocab, dict) or not vocab:
        return "vocabulary.json missing vocab"
    merges = model_section.get("merges")
    if not isinstance(merges, list) or not merges:
        return "vocabulary.json missing merges"
    missing_tokens = sorted(token for token in _REQUIRED_TOKENS if token not in vocab)
    if missing_tokens:
        return "missing tokens: " + ", ".join(missing_tokens)
    return None


def _validate_vocabulary_txt(path: Path) -> Optional[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - diagnostics only
        return f"read error: {exc}"
    if not content.strip():
        return "empty"
    missing_tokens = [token for token in _REQUIRED_TOKENS if token not in content]
    if missing_tokens:
        return "missing tokens: " + ", ".join(sorted(missing_tokens))
    return None


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        if name == "tokenizer.json":
            error = _validate_tokenizer(candidate)
        else:
            _, error = _load_json(candidate)
        if error:
            issues[name] = error

    vocabulary_path: Optional[Path] = None
    for vocab_name in VOCABULARY_CANDIDATES:
        candidate = path / vocab_name
        if candidate.exists() and candidate.is_file():
            vocabulary_path = candidate
            break

    if vocabulary_path is None:
        issues["vocabulary.json|vocabulary.txt"] = "missing"
    else:
        if vocabulary_path.stat().st_size == 0:
            issues[vocabulary_path.name] = "empty"
        else:
            if vocabulary_path.suffix == ".json":
                error = _validate_vocabulary_json(vocabulary_path)
            else:
                error = _validate_vocabulary_txt(vocabulary_path)
            if error:
                issues[vocabulary_path.name] = error

    return (not issues), issues


def _log_snapshot_diagnostics(path: Path, repo_id: str, revision: Optional[str]) -> None:
    if revision:
        log.info("Model %s revision %s", repo_id, revision)
    else:
        log.info("Model %s revision unknown", repo_id)
    entries: Iterable[Path]
    entries = list(sorted(path.glob(_MODEL_BIN_PATTERN)))
    entries += [path / name for name in ("config.json", "tokenizer.json")]
    for vocab_name in VOCABULARY_CANDIDATES:
        entries.append(path / vocab_name)
    for candidate in entries:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            sha = _compute_sha256(candidate)
            size = candidate.stat().st_size
            log.info("%s — size=%d bytes sha256=%s", candidate.name, size, sha)
        except Exception as exc:  # pragma: no cover - diagnostics only
            log.warning("Failed to compute diagnostics for %s: %s", candidate, exc)


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


def _rebuild_vocabulary(local_dir: Path) -> bool:
    tokenizer_path = local_dir / "tokenizer.json"
    vocabulary_path = local_dir / "vocabulary.json"
    data, error = _load_json(tokenizer_path)
    if data is None:
        log.error("Cannot rebuild vocabulary.json: tokenizer.json invalid (%s)", error)
        return False
    try:
        payload = _normalise_vocabulary_payload(data)
    except ValueError as exc:
        log.error("Cannot rebuild vocabulary.json: %s", exc)
        return False
    vocabulary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Generated vocabulary.json locally from tokenizer.json")
    return True


def _download_vocabulary(repo_id: str, local_dir: Path) -> None:
    try:
        hf_hub_download(
            repo_id=repo_id,
            filename="vocabulary.json",
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        return
    except HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        log.info("vocabulary.json not available upstream; trying vocabulary.txt")
    hf_hub_download(
        repo_id=repo_id,
        filename="vocabulary.txt",
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )


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
        if name == "vocabulary.json|vocabulary.txt":
            _status_callback(status_cb, "Перекачиваем словарь модели…")
            try:
                _download_vocabulary(repo_id, local_dir)
            except HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    log.warning("Neither vocabulary.json nor vocabulary.txt available; attempting local rebuild")
                    if not _rebuild_vocabulary(local_dir):
                        raise
                else:
                    raise
            continue
        _status_callback(status_cb, f"Перекачиваем {name}… ({issues[name]})")
        target = local_dir / name
        if target.exists():
            try:
                target.unlink()
            except Exception:
                pass
        try:
            hf_hub_download(
                repo_id=repo_id,
                filename=name,
                local_dir=str(local_dir),
                local_dir_use_symlinks=False,
                resume_download=True,
            )
        except HTTPError as exc:
            if name in VOCABULARY_CANDIDATES and exc.response is not None and exc.response.status_code == 404:
                log.warning("%s missing upstream; attempting alternative vocabulary download", name)
                try:
                    _download_vocabulary(repo_id, local_dir)
                except HTTPError:
                    if not _rebuild_vocabulary(local_dir):
                        raise
            else:
                raise


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

    revision: Optional[str] = None
    try:
        info = _HF_API.model_info(repo_id)
        revision = getattr(info, "sha", None)
    except Exception as exc:  # pragma: no cover - diagnostics only
        log.debug("Failed to fetch model info for %s: %s", repo_id, exc)

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
    full_refresh_performed = False
    while True:
        ok, issues = validate_snapshot(local_path)
        if ok:
            break
        attempts += 1
        if attempts == 1:
            _redownload_problem_files(repo_id, local_path, issues, on_status)
            continue
        if not full_refresh_performed:
            _status_callback(on_status, "Полная повторная загрузка модели…")
            for entry in local_path.iterdir():
                if entry.is_file():
                    try:
                        entry.unlink()
                    except Exception:
                        pass
                else:
                    shutil.rmtree(entry, ignore_errors=True)
            snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_path),
                local_dir_use_symlinks=False,
                allow_patterns=FILES,
                resume_download=False,
                max_workers=4,
                tqdm_class=None,
            )
            full_refresh_performed = True
            continue
        details = ", ".join(f"{name}: {reason}" for name, reason in issues.items())
        raise RuntimeError(f"Не удалось восстановить модель {repo_id}: {details}")

    if on_progress:
        try:
            on_progress(1, 1)
        except Exception:
            log.exception("progress callback failed")

    _log_snapshot_diagnostics(local_path, repo_id, revision)
    return str(local_path)


__all__ = ["ensure_model", "validate_snapshot", "VOCABULARY_CANDIDATES"]
