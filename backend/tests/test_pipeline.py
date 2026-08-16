import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services import media, minds, transcription
from app.services.pipeline import run_pipeline
from app.services.transcription import Transcription, TranscriptSegment

FAKE_SEGMENTS = [
    TranscriptSegment(text="hello world.", start=0.0, end=1.5),
    TranscriptSegment(text="this is a test.", start=1.5, end=3.0),
]


def _enable_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "true")
    get_settings.cache_clear()


def _stub_minds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    get_settings.cache_clear()
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {"brand_voice": "bold"})
    monkeypatch.setattr(
        minds,
        "generate_clip_metadata",
        lambda transcript, duration_seconds=None, memory_context=None, **kwargs: minds.ClipMetadata(
            virality_score=80,
            suggested_titles=["Title A", "Title B"],
            platform_hooks={"youtube_shorts": ["s"], "tiktok": ["t"], "x": ["x"]},
        ),
    )


def _stub_pipeline_stages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    _stub_minds(monkeypatch)
    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: raw)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: Transcription(segments=FAKE_SEGMENTS, duration_seconds=30.0),
    )
    monkeypatch.setattr(media, "cut_clip", lambda source, dest, start, end: dest.write_bytes(b"clip") or dest)
    monkeypatch.setattr(
        media,
        "extract_frame_at_timestamp",
        lambda source, dest, timestamp: dest.write_bytes(b"png") or dest,
    )
    return raw


def test_url_job_transitions_downloading_then_transcribing_and_persists_transcript(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    _stub_pipeline_stages(monkeypatch, tmp_path)

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/video.mp4", "title": "My video"},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert job["duration_seconds"] == 30.0
    assert job["transcript_segments"] == [
        {"text": "hello world.", "start": 0.0, "end": 1.5},
        {"text": "this is a test.", "start": 1.5, "end": 3.0},
    ]
    saved_raw = Path(job["file_path"])
    assert saved_raw.name == "video.mp4"
    assert saved_raw.is_relative_to(tmp_path / "raw")


def test_url_job_visits_downloading_and_extracting_clips_statuses(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    _stub_minds(monkeypatch)
    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    statuses_seen: list[str] = []

    from sqlalchemy import select

    from app.db.base import get_session_factory
    from app.models.job import Job

    def fake_download(url: str, target_dir: Path) -> Path:
        with get_session_factory()() as db:
            job = db.scalar(select(Job).where(Job.source_url == url))
            statuses_seen.append(job.status.value)
        return raw

    def fake_cut_clip(source: Path, dest: Path, start: float, end: float) -> Path:
        with get_session_factory()() as db:
            job = db.scalar(select(Job).where(Job.file_path == str(source)))
            statuses_seen.append(job.status.value)
        dest.write_bytes(b"clip")
        return dest

    monkeypatch.setattr(media, "download_video", fake_download)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: Transcription(segments=FAKE_SEGMENTS, duration_seconds=10.0),
    )
    monkeypatch.setattr(media, "cut_clip", fake_cut_clip)
    monkeypatch.setattr(
        media,
        "extract_frame_at_timestamp",
        lambda source, dest, timestamp: dest.write_bytes(b"png") or dest,
    )

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/statuses.mp4"},
    )
    job_id = res.json()["job_id"]

    assert statuses_seen == ["DOWNLOADING", "EXTRACTING_CLIPS"]
    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"


def test_upload_job_skips_download_and_uses_uploaded_file(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    _stub_pipeline_stages(monkeypatch, tmp_path)
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: pytest.fail("download called"))

    res = test_client.post(
        "/api/v1/jobs/process",
        files={"file": ("upload.mp4", b"fake media bytes", "video/mp4")},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert Path(job["file_path"]).name.endswith("upload.mp4")
    assert job["transcript_segments"][0]["text"] == "hello world."


def test_stage_failure_marks_job_failed_and_stops_pipeline(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    _enable_pipeline(monkeypatch)
    monkeypatch.setattr(
        media,
        "download_video",
        lambda url, target_dir: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/broken.mp4"},
    )
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert "network down" in job["error_message"]
    assert job["transcript_segments"] is None
    assert job["duration_seconds"] is None


def test_local_provider_job_completes_with_faster_whisper(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "local")
    _stub_minds(monkeypatch)
    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: raw)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(
        media, "cut_clip", lambda source, dest, start, end: dest.write_bytes(b"clip") or dest
    )
    monkeypatch.setattr(
        media,
        "extract_frame_at_timestamp",
        lambda source, dest, timestamp: dest.write_bytes(b"png") or dest,
    )

    class _FakeSegment:
        def __init__(self, text: str, start: float, end: float) -> None:
            self.text = text
            self.start = start
            self.end = end

    class _FakeInfo:
        duration = 30.0

    class _FakeModel:
        def transcribe(self, audio_path: str):
            return iter(
                [
                    _FakeSegment("hello world.", 0.0, 1.5),
                    _FakeSegment("this is a test.", 1.5, 3.0),
                ]
            ), _FakeInfo()

    monkeypatch.setattr(
        transcription, "_get_local_model", lambda model_size: _FakeModel()
    )

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/local.mp4"},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert job["duration_seconds"] == 30.0
    assert job["transcript_segments"] == [
        {"text": "hello world.", "start": 0.0, "end": 1.5},
        {"text": "this is a test.", "start": 1.5, "end": 3.0},
    ]


def test_missing_groq_api_key_fails_job_with_descriptive_message(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fake wav bytes")
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: raw)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/no-key.mp4"},
    )
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert "GROQ_API_KEY is not configured" in job["error_message"]
    assert job["transcript_segments"] is None


def test_process_unknown_job_is_a_noop(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    _enable_pipeline(monkeypatch)
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: pytest.fail("transcribe called"),
    )
    run_pipeline("does-not-exist")
    assert test_client.get("/api/v1/jobs/does-not-exist").status_code == 404


def test_unconfigured_minds_fails_job_at_scoring_stage(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    _stub_pipeline_stages(monkeypatch, tmp_path)
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "")
    get_settings.cache_clear()

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/no-minds.mp4"},
    )
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert "MINDS_BUILDER_API_KEY" in job["error_message"]
    assert "fail-closed" in job["error_message"]

    clips = test_client.get(f"/api/v1/jobs/{job_id}/clips").json()
    assert clips == []


def test_clip_less_job_fails_when_minds_unconfigured(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: raw)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: Transcription(segments=[], duration_seconds=10.0),
    )
    monkeypatch.setattr(
        media, "cut_clip", lambda source, dest, start, end: pytest.fail("cut called")
    )
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "")
    get_settings.cache_clear()

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/silent-no-minds.mp4"},
    )
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert "MINDS_BUILDER_API_KEY" in job["error_message"]
    assert test_client.get(f"/api/v1/jobs/{job_id}/clips").json() == []


def test_scoring_minds_error_fails_job(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    _stub_pipeline_stages(monkeypatch, tmp_path)

    def failing_metadata(transcript, duration_seconds=None, memory_context=None, **kwargs):
        raise minds.MindsError("builder api down")

    monkeypatch.setattr(minds, "generate_clip_metadata", failing_metadata)

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/flaky.mp4"},
    )
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert "builder api down" in job["error_message"]

    clips = test_client.get(f"/api/v1/jobs/{job_id}/clips").json()
    assert clips == []


def test_memory_fetch_failure_still_scores_without_context(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    _stub_pipeline_stages(monkeypatch, tmp_path)
    contexts: list[str | None] = []
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: (_ for _ in ()).throw(minds.MindsError("builder api down")),
    )

    def capturing_metadata(transcript, duration_seconds=None, memory_context=None, **kwargs):
        contexts.append(memory_context)
        return minds.ClipMetadata(
            virality_score=70,
            suggested_titles=["A"],
            platform_hooks={"youtube_shorts": [], "tiktok": [], "x": []},
        )

    monkeypatch.setattr(minds, "generate_clip_metadata", capturing_metadata)

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/degraded-memory.mp4"},
    )
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    clips = test_client.get(f"/api/v1/jobs/{job_id}/clips").json()
    assert all(clip["virality_score"] == 70 for clip in clips)
    assert contexts == [None]


def test_each_pipeline_run_uses_fresh_conversation_alias(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    _stub_pipeline_stages(monkeypatch, tmp_path)
    aliases: list[str] = []

    def capturing_metadata(transcript, duration_seconds=None, memory_context=None, **kwargs):
        aliases.append(kwargs.get("conversation_alias"))
        return minds.ClipMetadata(
            virality_score=70,
            suggested_titles=["A"],
            platform_hooks={"youtube_shorts": [], "tiktok": [], "x": []},
        )

    monkeypatch.setattr(minds, "generate_clip_metadata", capturing_metadata)

    first = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/alias-one.mp4"},
    ).json()["job_id"]
    second = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/alias-two.mp4"},
    ).json()["job_id"]

    assert test_client.get(f"/api/v1/jobs/{first}").json()["status"] == "COMPLETED"
    assert test_client.get(f"/api/v1/jobs/{second}").json()["status"] == "COMPLETED"

    assert len(aliases) == 2
    assert aliases[0] != aliases[1]
    for alias in aliases:
        assert alias is not None and alias.startswith(f"{minds.MESSAGING_ALIAS}-")
        assert len(alias) <= 64, "Builder API rejects aliases longer than 64 chars"
        assert re.fullmatch(r"[a-z0-9_-]+", alias)
