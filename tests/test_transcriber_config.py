from transcribatoraud import TranscriptionConfig


def test_transcription_kwargs_resolve_language():
    config = TranscriptionConfig(language="en")

    kwargs = config.transcription_kwargs()

    assert kwargs["language"] == "en"

    kwargs_override = config.transcription_kwargs(language="es")

    assert kwargs_override["language"] == "es"
    assert kwargs_override["beam_size"] == config.beam_size
    assert kwargs_override["vad_filter"] == config.vad_filter


def test_model_kwargs_contains_compute_type():
    config = TranscriptionConfig(compute_type="int8_float32")

    kwargs = config.model_kwargs()

    assert kwargs == {"compute_type": "int8_float32"}
