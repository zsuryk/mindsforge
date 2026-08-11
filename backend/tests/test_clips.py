from pathlib import Path

import pytest
from app.services.clips import build_clip_candidates
from app.services.transcription import TranscriptSegment
from fastapi.testclient import TestClient


def segments(*spans: tuple[float, float, str]) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(text=text, start=start, end=end) for start, end, text in spans
    ]


def test_empty_transcript_yields_no_candidates() -> None:
    assert build_clip_candidates([]) == []


def test_short_transcript_yields_single_candidate() -> None:
    candidates = build_clip_candidates(
        segments((0.0, 5.0, "hello world."), (5.0, 10.0, "this is a test."))
    )
    assert len(candidates) == 1
    assert candidates[0].start == 0.0
    assert candidates[0].end == 10.0
    assert candidates[0].transcript_text == "hello world. this is a test."


def test_flushes_on_sentence_boundary_once_min_duration_reached() -> None:
    spans = [(i * 8, (i + 1) * 8, "sentence.") for i in range(8)]
    candidates = build_clip_candidates(segments(*spans))
    assert [(c.start, c.end) for c in candidates] == [
        (0.0, 16.0),
        (16.0, 32.0),
        (32.0, 48.0),
        (48.0, 64.0),
    ]


def test_wait_for_later_sentence_boundary_when_under_min() -> None:
    spans = [
        (0, 5, "one."),
        (5, 10, "two"),
        (10, 15, "three"),
        (15, 20, "four."),
    ]
    candidates = build_clip_candidates(segments(*spans))
    assert [(c.start, c.end) for c in candidates] == [(0.0, 20.0)]


def test_hard_cuts_before_segment_that_exceeds_max_duration() -> None:
    spans = [(i * 8, (i + 1) * 8, "no punctuation") for i in range(8)]
    candidates = build_clip_candidates(segments(*spans))
    assert [(c.start, c.end) for c in candidates] == [(0.0, 56.0), (56.0, 64.0)]


def test_single_oversized_segment_is_capped_at_max_duration() -> None:
    candidates = build_clip_candidates(segments((0.0, 100.0, "one long rambling segment")))
    assert [(c.start, c.end) for c in candidates] == [(0.0, 60.0)]


def test_candidates_never_exceed_max_duration() -> None:
    spans = [(i * 4, (i + 1) * 4, "no punctuation here at all") for i in range(30)]
    candidates = build_clip_candidates(segments(*spans))
    assert candidates
    for candidate in candidates:
        assert candidate.end - candidate.start <= 60.0


def test_short_tail_folds_into_previous_candidate() -> None:
    spans = [(0, 20, "first sentence."), (20, 22, "trailing bit")]
    candidates = build_clip_candidates(segments(*spans))
    assert len(candidates) == 1
    assert candidates[0].end == 22.0
    assert candidates[0].transcript_text == "first sentence. trailing bit"


def test_tail_at_least_min_tail_duration_stands_alone() -> None:
    spans = [(0, 20, "first sentence."), (20, 27, "second long tail")]
    candidates = build_clip_candidates(segments(*spans))
    assert [(c.start, c.end) for c in candidates] == [(0.0, 20.0), (20.0, 27.0)]


def test_titles_truncate_to_eight_words() -> None:
    text = "one two three four five six seven eight nine ten."
    candidates = build_clip_candidates(
        segments((0.0, 1.0, text), (1.0, 2.0, "eleven twelve"))
    )
    assert candidates[0].title == "one two three four five six seven eight…"


def test_min_and_max_bounds_are_honored() -> None:
    spans = [(i * 2, (i + 1) * 2, f"chunk {i}.") for i in range(4)]
    candidates = build_clip_candidates(segments(*spans), min_duration=3.0, max_duration=5.0)
    assert [(c.start, c.end) for c in candidates] == [(0.0, 4.0), (4.0, 8.0)]


def test_full_pipeline_persists_clips_with_files_and_completes_job(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.services import media, transcription
    from app.services.transcription import Transcription, TranscriptSegment

    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: raw)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: Transcription(
            segments=[
                TranscriptSegment(text="hello world.", start=0.0, end=1.5),
                TranscriptSegment(text="this is a test.", start=1.5, end=3.0),
            ],
            duration_seconds=30.0,
        ),
    )

    cut_args: list[tuple[float, float]] = []

    def fake_cut(source: Path, dest: Path, start: float, end: float) -> Path:
        cut_args.append((start, end))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"clip bytes")
        return dest

    thumb_args: list[float] = []

    def fake_thumb(source: Path, dest: Path, timestamp: float) -> Path:
        thumb_args.append(timestamp)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"png bytes")
        return dest

    monkeypatch.setattr(media, "cut_clip", fake_cut)
    monkeypatch.setattr(media, "extract_frame_at_timestamp", fake_thumb)

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/video.mp4", "title": "My video"},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"

    clips_res = test_client.get(f"/api/v1/jobs/{job_id}/clips")
    assert clips_res.status_code == 200
    clips = clips_res.json()
    assert len(clips) == 1

    clip = clips[0]
    assert clip["job_id"] == job_id
    assert clip["title"] == "hello world. this is a test."
    assert clip["start_time"] == 0.0
    assert clip["end_time"] == 3.0
    assert clip["transcript_text"] == "hello world. this is a test."
    assert clip["video_url"] == f"/media/clips/{job_id}/{clip['id']}.mp4"
    assert clip["thumbnail_url"] == f"/media/clips/{job_id}/{clip['id']}.png"
    assert clip["virality_score"] is None
    assert clip["suggested_hooks"] is None
    assert cut_args == [(0.0, 3.0)]
    assert thumb_args == [1.0]

    media_dir = get_settings().MEDIA_DIR
    assert (media_dir / "clips" / job_id / f"{clip['id']}.mp4").read_bytes() == b"clip bytes"
    assert (media_dir / "clips" / job_id / f"{clip['id']}.png").read_bytes() == b"png bytes"

    detail = test_client.get(f"/api/v1/clips/{clip['id']}")
    assert detail.status_code == 200
    assert detail.json() == clip


def test_clips_endpoint_404s_for_unknown_job(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    assert test_client.get("/api/v1/jobs/unknown/clips").status_code == 404


def test_clip_detail_404s_for_unknown_clip(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    assert test_client.get("/api/v1/clips/unknown").status_code == 404


def test_job_without_speech_completes_without_clips(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.services import media, transcription
    from app.services.transcription import Transcription

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

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/silent.mp4"},
    )
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert test_client.get(f"/api/v1/jobs/{job_id}/clips").json() == []


def test_clip_cut_failure_marks_job_failed(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.services import media, transcription
    from app.services.transcription import Transcription, TranscriptSegment

    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: raw)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: Transcription(
            segments=[TranscriptSegment(text="hello.", start=0.0, end=20.0)],
            duration_seconds=20.0,
        ),
    )
    monkeypatch.setattr(
        media,
        "cut_clip",
        lambda source, dest, start, end: (_ for _ in ()).throw(RuntimeError("encoder boom")),
    )

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/boom.mp4"},
    )
    job_id = res.json()["job_id"]

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert "encoder boom" in job["error_message"]
    assert test_client.get(f"/api/v1/jobs/{job_id}/clips").json() == []


def test_rerunning_pipeline_clears_stale_error_message(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.pipeline import run_pipeline
    from sqlalchemy import select

    from app.db.base import get_session_factory
    from app.models.job import Job

    test_client, tmp_path = client
    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.services import media, transcription
    from app.services.transcription import Transcription, TranscriptSegment

    raw = tmp_path / "raw" / "video.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"fake media bytes")
    monkeypatch.setattr(media, "download_video", lambda url, target_dir: raw)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest)
    monkeypatch.setattr(media, "cut_clip", lambda source, dest, start, end: dest.write_bytes(b"x") or dest)
    monkeypatch.setattr(
        media,
        "extract_frame_at_timestamp",
        lambda source, dest, timestamp: dest.write_bytes(b"x") or dest,
    )

    def fake_transcribe(audio_path: Path):
        raise RuntimeError("transient failure")

    monkeypatch.setattr(transcription, "transcribe", fake_transcribe)

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/retry.mp4"},
    )
    job_id = res.json()["job_id"]
    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert "transient failure" in job["error_message"]

    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda audio_path: Transcription(
            segments=[TranscriptSegment(text="all good.", start=0.0, end=20.0)],
            duration_seconds=20.0,
        ),
    )
    with get_session_factory()() as db:
        stored = db.scalar(select(Job).where(Job.id == job_id))
        stored.status = "PENDING"
        db.commit()
    run_pipeline(job_id)

    job = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert job["error_message"] is None
    assert len(test_client.get(f"/api/v1/jobs/{job_id}/clips").json()) == 1
