"""Batch processing utilities."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from app.core import audio, exporter
from app.core.asr import Word, transcribe_to_words
from app.core.logging import setup_logging

_ROOT_LOGGER = setup_logging()
_LOGGER = _ROOT_LOGGER.getChild("batch")

ProgressCallback = Callable[[Path, str], None]


@dataclass(slots=True)
class BatchOptions:
    output_dir: Path
    formats: Sequence[str]
    model: str
    device: str
    compute_type: str
    language: Optional[str]
    keep_punct: bool
    vad: bool
    beam_size: int = 5
    parallel: int = 1
    skip_existing: bool = False


@dataclass(slots=True)
class BatchResult:
    source: Path
    status: str
    duration: Optional[float]
    outputs: Dict[str, Path] = field(default_factory=dict)
    error: Optional[str] = None
    words: int = 0

    @property
    def success(self) -> bool:
        return self.status == "completed"


def _resolve_outputs(source: Path, destination_dir: Path, formats: Sequence[str]) -> Dict[str, Path]:
    outputs: Dict[str, Path] = {}
    for fmt in formats:
        target = destination_dir / f"{source.stem}.words.{fmt}"
        outputs[fmt] = target
    return outputs


def discover_inputs(source: Path, recursive: bool = False) -> List[Path]:
    """Discover audio files matching the source definition."""

    path = Path(source)
    pattern = str(path)
    has_wildcard = any(symbol in pattern for symbol in "*?[]")

    candidates: List[Path] = []
    if has_wildcard:
        base = path.parent if path.parent != Path("") else Path.cwd()
        candidates.extend(
            candidate
            for candidate in base.glob(path.name)
            if candidate.is_file() and audio.is_supported_audio(candidate)
        )
    elif path.is_dir():
        iterator = path.rglob("*") if recursive else path.glob("*")
        candidates.extend(
            candidate
            for candidate in iterator
            if candidate.is_file() and audio.is_supported_audio(candidate)
        )
    elif path.is_file():
        if audio.is_supported_audio(path):
            candidates.append(path)
    else:
        _LOGGER.warning("Input %s not found or unsupported", source)

    return sorted({candidate.resolve() for candidate in candidates})


def _export_words(words: List[Word], outputs: Dict[str, Path]) -> None:
    for fmt, destination in outputs.items():
        exporter.EXPORTERS[fmt](words, destination)


def _process_single(path: Path, options: BatchOptions) -> BatchResult:
    outputs = _resolve_outputs(path, options.output_dir, options.formats)
    if options.skip_existing and all(destination.exists() for destination in outputs.values()):
        return BatchResult(source=path, status="skipped", duration=audio.probe_duration(path), outputs=outputs)

    try:
        words = transcribe_to_words(
            path,
            model=options.model,
            device=options.device,
            compute_type=options.compute_type,
            language=options.language,
            keep_punct=options.keep_punct,
            vad=options.vad,
            beam_size=options.beam_size,
        )
        _export_words(words, outputs)
        return BatchResult(
            source=path,
            status="completed",
            duration=audio.probe_duration(path),
            outputs=outputs,
            words=len(words),
        )
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to process %s", path)
        return BatchResult(
            source=path,
            status="failed",
            duration=audio.probe_duration(path),
            outputs=outputs,
            error=str(exc),
        )


def process_batch(
    paths: Iterable[Path],
    options: BatchOptions,
    progress: Optional[ProgressCallback] = None,
) -> List[BatchResult]:
    """Process the given paths with the provided options."""

    resolved_paths = [Path(item).resolve() for item in paths]
    if not resolved_paths:
        return []

    options.output_dir.mkdir(parents=True, exist_ok=True)
    formats = exporter.normalise_formats(options.formats)
    options = BatchOptions(
        output_dir=options.output_dir,
        formats=formats,
        model=options.model,
        device=options.device,
        compute_type=options.compute_type,
        language=options.language,
        keep_punct=options.keep_punct,
        vad=options.vad,
        beam_size=options.beam_size,
        parallel=max(1, options.parallel),
        skip_existing=options.skip_existing,
    )

    for path in resolved_paths:
        if progress:
            progress(path, "queued")

    results: List[BatchResult] = []
    with ThreadPoolExecutor(max_workers=options.parallel) as executor:
        future_to_path: Dict[Future[BatchResult], Path] = {}
        for path in resolved_paths:
            future = executor.submit(_worker_wrapper, path, options, progress)
            future_to_path[future] = path
        for future in as_completed(future_to_path):
            result = future.result()
            results.append(result)
    return results


def _worker_wrapper(path: Path, options: BatchOptions, progress: Optional[ProgressCallback]) -> BatchResult:
    if progress:
        progress(path, "processing")
    result = _process_single(path, options)
    if progress:
        progress(path, result.status)
    return result

