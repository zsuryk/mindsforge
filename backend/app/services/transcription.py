from dataclasses import dataclass
from pathlib import Path

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


def transcribe(audio_path: Path) -> Transcription:
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
