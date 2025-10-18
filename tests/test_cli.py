from __future__ import annotations

from pathlib import Path
import sys
import types


class _StubTqdm:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def update(self, _value: int) -> None:
        pass


_tqdm_module = types.ModuleType("tqdm")
_tqdm_module.tqdm = _StubTqdm
sys.modules.setdefault("tqdm", _tqdm_module)


import app.cli as cli
from app.core.batch import BatchResult


def _mock_success_result(source: Path) -> BatchResult:
    return BatchResult(source=source, status="completed", duration=None, outputs={}, words=0)


def test_run_cli_defaults_to_input_directory(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    audio_file = input_dir / "sample.wav"
    audio_file.touch()

    captured = {}

    def fake_discover_inputs(source: Path, recursive: bool):
        assert source == input_dir
        return [audio_file]

    def fake_process_batch(paths, options, progress=None):
        captured["output_dir"] = options.output_dir
        return [_mock_success_result(audio_file)]

    monkeypatch.setattr(cli, "discover_inputs", fake_discover_inputs)
    monkeypatch.setattr(cli, "process_batch", fake_process_batch)
    monkeypatch.setattr(cli, "tqdm", _StubTqdm)

    exit_code = cli.run_cli(["--input", str(input_dir)])

    assert exit_code == 0
    assert captured["output_dir"] == input_dir


def test_run_cli_defaults_to_pattern_parent(tmp_path, monkeypatch):
    input_dir = tmp_path / "nested"
    input_dir.mkdir()
    audio_file = input_dir / "clip.wav"
    audio_file.touch()
    pattern = input_dir / "*.wav"

    captured = {}

    def fake_discover_inputs(source: Path, recursive: bool):
        assert source == Path(pattern)
        return [audio_file]

    def fake_process_batch(paths, options, progress=None):
        captured["output_dir"] = options.output_dir
        return [_mock_success_result(audio_file)]

    monkeypatch.setattr(cli, "discover_inputs", fake_discover_inputs)
    monkeypatch.setattr(cli, "process_batch", fake_process_batch)
    monkeypatch.setattr(cli, "tqdm", _StubTqdm)

    exit_code = cli.run_cli(["--input", str(pattern)])

    assert exit_code == 0
    assert captured["output_dir"] == input_dir


def test_check_ffmpeg_success(monkeypatch, capsys, tmp_path):
    ffmpeg_path = tmp_path / "ffmpeg.exe"
    ffmpeg_path.write_text("")

    monkeypatch.setattr(cli, "find_ffmpeg", lambda: ffmpeg_path)

    exit_code = cli.run_cli(["--check-ffmpeg"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(ffmpeg_path) in captured.out


def test_check_ffmpeg_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "find_ffmpeg", lambda: None)

    exit_code = cli.run_cli(["--check-ffmpeg"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "FFmpeg" in captured.err
