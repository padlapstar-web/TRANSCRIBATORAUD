"""Quick sanity check ensuring model download + init succeed."""
from __future__ import annotations

from app.core.worker import load_whisper


def main() -> None:
    model, device, compute, _ = load_whisper(
        "Systran/faster-whisper-tiny",
        prefer_cuda=True,
        compute_type_cuda="float16",
        compute_type_cpu="int8",
        timeout_sec=180,
    )
    print("OK:", model is not None, device, compute)


if __name__ == "__main__":
    main()
