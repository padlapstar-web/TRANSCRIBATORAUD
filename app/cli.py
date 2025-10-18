"""Command line interface for TRANSCRIBATORAUD."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Sequence

from tqdm import tqdm

from app.core import exporter
from app.core.batch import BatchOptions, discover_inputs, process_batch
from app.core.logging import setup_logging
from app.core.ffmpeg import find_ffmpeg

_ROOT_LOGGER = setup_logging()
_LOGGER = _ROOT_LOGGER.getChild("cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcribatoraud",
        description="Offline batch transcription tool.",
    )
    parser.add_argument(
        "--input",
        required=False,
        help="Path to an audio file, directory, or glob mask (e.g. *.wav)",
    )
    parser.add_argument(
        "--out",
        dest="output",
        default=None,
        help="Directory to store transcription outputs (defaults to the input directory).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively scan folders when --input points to a directory.",
    )
    parser.add_argument(
        "--formats",
        default="jsonl",
        help="Comma separated list of export formats: jsonl,csv,vtt,srt,lrc",
    )
    parser.add_argument("--model", default="base", help="Local Whisper model name.")
    parser.add_argument(
        "--device",
        default="auto",
        help="Device for inference (auto, cpu or cuda).",
    )
    parser.add_argument(
        "--compute_type",
        default="auto",
        help="CTranslate2 compute type (auto, int8, float16, float32, ...).",
    )
    parser.add_argument(
        "--language",
        default="auto",
        help="Language hint (auto, ru, en, ...).",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Beam size for beam-search decoding.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of files to process in parallel.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files whose outputs already exist.",
    )
    parser.add_argument(
        "--keep-punct",
        dest="keep_punct",
        action="store_true",
        default=True,
        help="Keep punctuation marks in recognised words (default).",
    )
    parser.add_argument(
        "--no-keep-punct",
        dest="keep_punct",
        action="store_false",
        help="Strip punctuation from recognised words.",
    )
    parser.add_argument(
        "--vad",
        action="store_true",
        help="Enable VAD filtering to drop silence segments.",
    )
    parser.add_argument(
        "--check-ffmpeg",
        action="store_true",
        help="Check whether FFmpeg is discoverable and exit.",
    )
    return parser


def _parse_formats(raw: str) -> list[str]:
    return exporter.normalise_formats(raw.split(","))


def run_cli(args: Iterable[str]) -> int:
    parser = build_parser()
    namespace = parser.parse_args(list(args))

    if namespace.check_ffmpeg:
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            print(f"FFmpeg: {ffmpeg_path}")
            return 0
        print(
            "FFmpeg не найден. Установите ffmpeg и добавьте его в PATH или переменные окружения.",
            file=sys.stderr,
        )
        return 2

    source_input = namespace.input
    if not source_input:
        parser.error("--input обязательно, если не используется --check-ffmpeg")
        return 2  # pragma: no cover - parser.error завершает выполнение

    source = Path(source_input)
    if namespace.output:
        output_dir = Path(namespace.output)
    elif source.is_file():
        output_dir = source.parent
    elif source.is_dir():
        output_dir = source
    else:
        parent = source.parent
        output_dir = parent if str(parent) not in {"", "."} else Path.cwd()

    try:
        formats = _parse_formats(namespace.formats)
    except ValueError as exc:
        parser.error(str(exc))
        return 2  # pragma: no cover - parser.error exits

    inputs = discover_inputs(source, recursive=namespace.recursive)
    if not inputs:
        parser.error("No audio files found for the provided input")
        return 2  # pragma: no cover - parser.error exits

    options = BatchOptions(
        output_dir=output_dir,
        formats=formats,
        model=namespace.model,
        device=namespace.device,
        compute_type=namespace.compute_type,
        language=None if namespace.language.lower() == "auto" else namespace.language,
        keep_punct=namespace.keep_punct,
        vad=namespace.vad,
        beam_size=max(1, namespace.beam_size),
        parallel=max(1, namespace.parallel),
        skip_existing=namespace.skip_existing,
    )

    _LOGGER.info("Processing %d file(s)...", len(inputs))
    with tqdm(total=len(inputs), desc="Transcribing", unit="file") as progress_bar:
        def _progress_callback(path: Path, status: str) -> None:
            if status in {"completed", "failed", "skipped"}:
                progress_bar.update(1)

        results = process_batch(inputs, options, progress=_progress_callback)

    failures = [result for result in results if not result.success]
    for result in results:
        if result.success:
            exported = ", ".join(f"{fmt}:{path.name}" for fmt, path in result.outputs.items())
            print(f"✔ {result.source.name} → {exported}")
        elif result.status == "skipped":
            print(f"↷ {result.source.name} skipped (outputs exist)")
        else:
            print(f"✖ {result.source.name}: {result.error}")

    return 0 if not failures else 1


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv or [])

