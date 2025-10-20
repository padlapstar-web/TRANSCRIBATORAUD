from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.asr import Word
from app.core import exporter


@pytest.fixture()
def sample_words() -> list[Word]:
    return [
        Word(index=1, start=0.512, end=0.840, word="пример", probability=0.93),
        Word(index=2, start=0.840, end=1.420, word="тест", probability=0.87),
        Word(index=3, start=1.420, end=2.000, word="готов.", probability=None),
    ]


def test_save_jsonl(tmp_path: Path, sample_words: list[Word]) -> None:
    destination = tmp_path / "words.jsonl"
    exporter.save_jsonl(sample_words, destination)
    lines = destination.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(sample_words)
    first = json.loads(lines[0])
    assert first == {
        "i": 1,
        "start": pytest.approx(0.512),
        "end": pytest.approx(0.840),
        "word": "пример",
        "prob": pytest.approx(0.93),
    }


def test_save_csv(tmp_path: Path, sample_words: list[Word]) -> None:
    destination = tmp_path / "words.csv"
    exporter.save_csv(sample_words, destination)
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "i,start,end,word,prob"
    assert lines[1].split(",")[:4] == ["1", "0.512", "0.840", "пример"]
    assert lines[3].split(",")[-1] == ""


def test_save_vtt(tmp_path: Path, sample_words: list[Word]) -> None:
    destination = tmp_path / "words.vtt"
    exporter.save_vtt(sample_words, destination)
    content = destination.read_text(encoding="utf-8")
    assert content.startswith("WEBVTT")
    assert "00:00:00.512 --> 00:00:00.840" in content


def test_save_srt(tmp_path: Path, sample_words: list[Word]) -> None:
    destination = tmp_path / "words.srt"
    exporter.save_srt(sample_words, destination)
    content = destination.read_text(encoding="utf-8")
    assert "1\n00:00:00,512 --> 00:00:00,840" in content
    assert "3\n00:00:01,420 --> 00:00:02,000" in content


def test_save_lrc(tmp_path: Path, sample_words: list[Word]) -> None:
    destination = tmp_path / "words.lrc"
    exporter.save_lrc(sample_words, destination)
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("[00:00.51]")
    assert lines[-1].endswith("готов.")

