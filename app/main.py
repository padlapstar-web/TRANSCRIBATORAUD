"""FastAPI application exposing the transcription service."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from transcribatoraud import (
    TranscriptionResult,
    TranscriptionSegment,
    WhisperTranscriber,
)

app = FastAPI(title="Transcribator", version="0.1.0")


def get_transcriber() -> WhisperTranscriber:
    if not hasattr(app.state, "transcriber"):
        app.state.transcriber = WhisperTranscriber()
    return app.state.transcriber  # type: ignore[return-value]


class SegmentResponse(BaseModel):
    start: float
    end: float
    text: str
    probability: float | None = None

    @classmethod
    def from_domain(cls, segment: TranscriptionSegment) -> "SegmentResponse":
        return cls(
            start=segment.start,
            end=segment.end,
            text=segment.text,
            probability=segment.probability,
        )


class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[SegmentResponse]

    @classmethod
    def from_domain(cls, result: TranscriptionResult) -> "TranscriptionResponse":
        return cls(
            text=result.text,
            language=result.language,
            duration=result.duration,
            segments=[SegmentResponse.from_domain(seg) for seg in result.segments],
        )


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str | None = None,
    transcriber: Annotated[WhisperTranscriber, Depends(get_transcriber)] = None,  # type: ignore assignment
) -> JSONResponse:
    """Accept an audio file upload and return the transcription."""

    if transcriber is None:  # pragma: no cover - FastAPI guarantees dependency
        transcriber = WhisperTranscriber()

    try:
        suffix = Path(file.filename or "audio").suffix or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            temp_path = Path(tmp.name)
    except Exception as exc:  # pragma: no cover - fastapi handles request errors
        raise HTTPException(status_code=400, detail="Unable to read uploaded file") from exc

    try:
        result = transcriber.transcribe(temp_path, language=language)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Uploaded file could not be processed")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    return JSONResponse(TranscriptionResponse.from_domain(result).model_dump())


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
