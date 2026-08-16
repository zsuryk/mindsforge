from dataclasses import dataclass
from pathlib import Path
from typing import Any

from groq import Groq

from app.core.config import get_settings


class TranscriptionError(RuntimeError):
    pass


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float


@dataclass
class Transcription:
    segments: list[TranscriptSegment]
    duration_seconds: float


_local_models: dict[str, Any] = {}


def _get_local_model(model_size: str) -> Any:
    model = _local_models.get(model_size)
    if model is None:
        from faster_whisper import WhisperModel

        settings = get_settings()
        model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            use_auth_token=settings.HF_TOKEN or None,
        )
        _local_models[model_size] = model
    return model


def _transcribe_local(audio_path: Path) -> Transcription:
    try:
        model = _get_local_model(get_settings().WHISPER_MODEL)
    except Exception as exc:
        raise TranscriptionError(f"Local Whisper model load failed: {exc}") from exc

    try:
        segments_iter, info = model.transcribe(str(audio_path))
        segments = [
            TranscriptSegment(
                text=segment.text.strip(),
                start=float(segment.start),
                end=float(segment.end),
            )
            for segment in segments_iter
        ]
        return Transcription(
            segments=segments, duration_seconds=float(info.duration)
        )
    except Exception as exc:
        raise TranscriptionError(f"Local Whisper transcription failed: {exc}") from exc


def _transcribe_groq(audio_path: Path) -> Transcription:
    api_key = get_settings().GROQ_API_KEY
    if not api_key:
        raise TranscriptionError("GROQ_API_KEY is not configured")

    client = Groq(api_key=api_key)
    try:
        with audio_path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                response_format="verbose_json",
            )
    except Exception as exc:
        raise TranscriptionError(f"Groq transcription failed: {exc}") from exc

    data = response.model_dump()
    segments = [
        TranscriptSegment(text=s["text"], start=float(s["start"]), end=float(s["end"]))
        for s in data.get("segments") or []
    ]
    return Transcription(
        segments=segments, duration_seconds=float(data.get("duration") or 0.0)
    )


def transcribe(audio_path: Path) -> Transcription:
    provider = get_settings().TRANSCRIPTION_PROVIDER
    if provider == "groq":
        return _transcribe_groq(audio_path)
    if provider == "local":
        return _transcribe_local(audio_path)
    raise TranscriptionError(
        f"Unknown TRANSCRIPTION_PROVIDER: {provider!r} (expected 'groq' or 'local')"
    )