from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app.services.transcription import TranscriptionError, transcribe


class _Transcriptions:
    def create(self, model: str, file, response_format: str) -> SimpleNamespace:
        assert model == "whisper-large-v3"
        assert response_format == "verbose_json"
        return SimpleNamespace(
            duration=42.5,
            segments=[
                SimpleNamespace(text="first segment", start=0.0, end=2.0),
                SimpleNamespace(text="second segment", start=2.0, end=4.5),
            ],
        )


class _Audio:
    transcriptions = _Transcriptions()


class _FakeGroq:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    audio = _Audio()


class _ExplodingTranscriptions:
    def create(self, **kwargs) -> None:
        raise RuntimeError("groq is down")


class _ExplodingAudio:
    transcriptions = _ExplodingTranscriptions()


class _ExplodingGroq:
    def __init__(self, api_key: str) -> None:
        pass

    audio = _ExplodingAudio()


def test_transcribe_maps_verbose_json_to_segments(tmp_path, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")

    with patch("app.services.transcription.Groq", _FakeGroq):
        result = transcribe(audio)

    assert result.duration_seconds == 42.5
    assert [(s.text, s.start, s.end) for s in result.segments] == [
        ("first segment", 0.0, 2.0),
        ("second segment", 2.0, 4.5),
    ]


def test_transcribe_requires_api_key(tmp_path, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")

    with pytest.raises(TranscriptionError, match="GROQ_API_KEY"):
        transcribe(audio)


def test_transcribe_wraps_api_errors(tmp_path, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")

    with patch("app.services.transcription.Groq", _ExplodingGroq), pytest.raises(
        TranscriptionError, match="groq is down"
    ):
        transcribe(audio)
