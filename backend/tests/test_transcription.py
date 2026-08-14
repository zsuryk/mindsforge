from unittest.mock import patch

import pytest
from groq.types.audio.transcription import Transcription

from app.services.transcription import TranscriptionError, transcribe


class _Transcriptions:
    def create(self, model: str, file, response_format: str) -> Transcription:
        assert model == "whisper-large-v3"
        assert response_format == "verbose_json"
        return Transcription.model_validate(
            {
                "text": "first segment second segment",
                "duration": 42.5,
                "language": "english",
                "segments": [
                    {"text": "first segment", "start": 0.0, "end": 2.0},
                    {"text": "second segment", "start": 2.0, "end": 4.5},
                ],
            }
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


def test_transcribe_parses_segments_from_real_groq_response(
    tmp_path, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")

    payload = {
        "text": "hello world",
        "duration": 3.5,
        "language": "english",
        "segments": [
            {"text": "hello", "start": 0.0, "end": 1.2},
            {"text": "world", "start": 1.2, "end": 2.0},
        ],
    }

    class _RealResponseGroq:
        def __init__(self, api_key: str) -> None:
            pass

        class audio:
            class transcriptions:
                @staticmethod
                def create(**kwargs) -> Transcription:
                    return Transcription.model_validate(payload)

    with patch("app.services.transcription.Groq", _RealResponseGroq):
        result = transcribe(audio)

    assert result.duration_seconds == 3.5
    assert [(s.text, s.start, s.end) for s in result.segments] == [
        ("hello", 0.0, 1.2),
        ("world", 1.2, 2.0),
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

    with (
        patch("app.services.transcription.Groq", _ExplodingGroq),
        pytest.raises(TranscriptionError, match="groq is down"),
    ):
        transcribe(audio)
