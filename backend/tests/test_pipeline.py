from pathlib import Path

import pytest
from app.core.config import get_settings
from app.services import media, transcription
from app.services.pipeline import run_pipeline
from app.services.transcription import Transcription, TranscriptSegment
from fastapi.testclient import TestClient

FAKE_SEGMENTS = [
    TranscriptSegment(text="hello world", start=0.0, end=1.5),
    TranscriptSegment(text="this is a test", start=1.5, end=3.0),
]


def _enable_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "true")
    get_settings.cache_clear()


def _stub_pipeline_stages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fake wav bytes")
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: raw)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: Transcription(segments=FAKE_SEGMENTS, duration_seconds=30.0),
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
    assert job["status"] == "TRANSCRIBING"
    assert job["duration_seconds"] == 30.0
    assert job["transcript_segments"] == [
        {"text": "hello world", "start": 0.0, "end": 1.5},
        {"text": "this is a test", "start": 1.5, "end": 3.0},
    ]
    saved_raw = Path(job["file_path"])
    assert saved_raw.name == "video.mp4"
    assert saved_raw.is_relative_to(tmp_path / "raw")


def test_url_job_visits_downloading_status_before_transcribing(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    _enable_pipeline(monkeypatch)
    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    statuses_seen: list[str] = []

    from app.db.base import get_session_factory
    from app.models.job import Job
    from sqlalchemy import select

    def fake_download(url: str, target_dir: Path) -> Path:
        with get_session_factory()() as db:
            job = db.scalar(select(Job).where(Job.source_url == url))
            statuses_seen.append(job.status.value)
        return raw

    monkeypatch.setattr(media, "download_video", fake_download)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: Transcription(segments=FAKE_SEGMENTS, duration_seconds=10.0),
    )

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/statuses.mp4"},
    )
    job_id = res.json()["job_id"]

    assert statuses_seen == ["DOWNLOADING"]
    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "TRANSCRIBING"


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
    assert job["status"] == "TRANSCRIBING"
    assert Path(job["file_path"]).name.endswith("upload.mp4")
    assert job["transcript_segments"][0]["text"] == "hello world"


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
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
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
