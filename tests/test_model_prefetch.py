import json
from pathlib import Path

import pytest

pytest.importorskip("huggingface_hub")

from app.core import model_prefetch


class _DummyInfo:
    sha = "deadbeef"


class _DummyApi:
    def model_info(self, _repo_id: str):
        return _DummyInfo()


@pytest.fixture(autouse=True)
def _stub_hf_api(monkeypatch):
    monkeypatch.setattr(model_prefetch, "_HF_API", _DummyApi())


def _write_tokenizer(path: Path) -> None:
    payload = {
        "model": {
            "type": "BPE",
            "vocab": {
                "a": 0,
                "<|startoftranscript|>": 1,
                "<|endoftext|>": 2,
                "<|nospeech|>": 3,
                "<|notimestamps|>": 4,
            },
            "merges": ["a b"],
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_vocabulary(path: Path) -> None:
    payload = {
        "model": {
            "vocab": {
                "a": 0,
                "<|startoftranscript|>": 1,
                "<|endoftext|>": 2,
                "<|nospeech|>": 3,
                "<|notimestamps|>": 4,
            },
            "merges": ["a b"],
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validate_snapshot_requires_vocabulary(tmp_path: Path) -> None:
    (tmp_path / "model.bin").write_bytes(b"dummy")
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    _write_tokenizer(tmp_path / "tokenizer.json")
    ok, issues = model_prefetch.validate_snapshot(tmp_path)
    assert not ok
    assert "vocabulary.json|vocabulary.txt" in issues


def test_ensure_model_recovers_missing_vocabulary(monkeypatch, tmp_path: Path) -> None:
    repo_id = "dummy/repo"

    def fake_snapshot_download(**kwargs):
        directory = Path(kwargs["local_dir"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "model.bin").write_bytes(b"bin")
        (directory / "config.json").write_text("{}", encoding="utf-8")
        _write_tokenizer(directory / "tokenizer.json")

    created_vocab: Path | None = None

    def fake_hf_hub_download(**kwargs):
        nonlocal created_vocab
        directory = Path(kwargs["local_dir"])
        if kwargs["filename"] == "vocabulary.json":
            created_vocab = directory / "vocabulary.json"
            _write_vocabulary(created_vocab)
            return str(created_vocab)
        raise AssertionError("unexpected download request")

    monkeypatch.setattr(model_prefetch, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(model_prefetch, "hf_hub_download", fake_hf_hub_download)

    result = model_prefetch.ensure_model(repo_id, str(tmp_path))
    assert Path(result, "vocabulary.json").is_file()
    assert created_vocab is not None


def test_ensure_model_downloads_vocabulary_txt_when_available(monkeypatch, tmp_path: Path) -> None:
    repo_id = "dummy/repo"

    def fake_snapshot_download(**kwargs):
        directory = Path(kwargs["local_dir"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "model.bin").write_bytes(b"bin")
        (directory / "config.json").write_text("{}", encoding="utf-8")
        _write_tokenizer(directory / "tokenizer.json")

    def fake_hf_hub_download(**kwargs):
        filename = kwargs["filename"]
        directory = Path(kwargs["local_dir"])
        if filename == "vocabulary.json":
            from requests import HTTPError

            class _Resp:
                status_code = 404

            raise HTTPError(response=_Resp())
        if filename == "vocabulary.txt":
            path = directory / "vocabulary.txt"
            payload = "\n".join([
                "<|startoftranscript|>",
                "<|endoftext|>",
                "<|nospeech|>",
                "<|notimestamps|>",
            ])
            path.write_text(payload, encoding="utf-8")
            return str(path)
        raise AssertionError("unexpected download request")

    monkeypatch.setattr(model_prefetch, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(model_prefetch, "hf_hub_download", fake_hf_hub_download)

    result = model_prefetch.ensure_model(repo_id, str(tmp_path))
    vocab_txt = Path(result, "vocabulary.txt")
    assert vocab_txt.is_file()


def test_ensure_model_rebuilds_vocabulary_when_not_available(monkeypatch, tmp_path: Path) -> None:
    repo_id = "dummy/repo"

    def fake_snapshot_download(**kwargs):
        directory = Path(kwargs["local_dir"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "model.bin").write_bytes(b"bin")
        (directory / "config.json").write_text("{}", encoding="utf-8")
        _write_tokenizer(directory / "tokenizer.json")

    class _Resp:
        status_code = 404

    def fake_hf_hub_download(**kwargs):
        from requests import HTTPError

        raise HTTPError(response=_Resp())

    monkeypatch.setattr(model_prefetch, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(model_prefetch, "hf_hub_download", fake_hf_hub_download)

    result = model_prefetch.ensure_model(repo_id, str(tmp_path))
    vocab_path = Path(result, "vocabulary.json")
    assert vocab_path.is_file()
    data = json.loads(vocab_path.read_text(encoding="utf-8"))
    assert ("model" in data and "vocab" in data["model"]) or ("vocabulary" in data.get("model", {}))
