from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import get_session_factory
from app.models.adaptation import ClipAdaptation
from app.models.clip import Clip
from app.models.job import Job
from app.models.todo import TodoItemType
from app.services import adaptations, llm, minds, todo as todo_module

YOUTUBE_LONG_FORM_FEATURES = {
    "chapters": [{"title": "The hook", "timestamp": 2.0}],
    "tags": ["editing", "storytime"],
    "poll": {"question": "Which ending?", "options": ["A", "B"]},
    "quiz": [{"question": "What changed?", "answer": "Everything"}],
    "thumbnail_briefs": [
        {"frame_timestamp": 1.0, "overlay_text": "Wait for it"},
        {"frame_timestamp": 2.0, "overlay_text": "The reveal"},
        {"frame_timestamp": 3.0, "overlay_text": "You won't believe"},
    ],
    "shorts_link": "Why I left YouTube",
}


@pytest.fixture()
def _minds_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_clip(db, tmp_path: Path, title: str = "Adaptation clip") -> Clip:
    job = db.get(Job, "job-1")
    if job is None:
        job = Job(
            id="job-1",
            title="Source video",
            source_url="https://example.com/video",
            transcript_segments=[
                {"text": "one.", "start": 0.0, "end": 3.0},
                {"text": "two.", "start": 3.0, "end": 34.0},
            ],
        )
        db.add(job)
        db.commit()
        db.refresh(job)
    media_dir = tmp_path / "media" / "clips" / "job-1"
    media_dir.mkdir(parents=True, exist_ok=True)
    video = media_dir / "clip.mp4"
    video.write_bytes(b"video")
    clip = Clip(
        id=str(uuid4()),
        job_id=job.id,
        title=title,
        start_time=2.0,
        end_time=32.0,
        transcript_text="one.",
        file_path=str(video),
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def stub_features(
    monkeypatch: pytest.MonkeyPatch,
    *,
    features: dict | None = None,
    error: Exception | None = None,
) -> None:
    def generate(
        clip, platform, surface, segments, chat_context=None, conversation_alias=None
    ):
        if error is not None:
            raise error
        return llm.AdaptationFeatures(
            platform=platform, surface=surface, **(features or {})
        )

    monkeypatch.setattr(llm, "generate_adaptation_features", generate)


def stub_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.adaptations.render_adaptation_assets",
        lambda adaptation: {"thumbnail_variants": []},
    )


def test_generate_adaptation_runs_lifecycle_to_ready(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    stub_features(monkeypatch, features=YOUTUBE_LONG_FORM_FEATURES)
    stub_rendering(monkeypatch)
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/youtube/LONG_FORM")

    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "PENDING"
    assert body["features"] is None
    adaptation_id = body["id"]

    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}")
    assert detail.status_code == 200
    ready = detail.json()
    assert ready["status"] == "READY"
    assert ready["platform"] == "youtube"
    assert ready["surface"] == "LONG_FORM"
    assert ready["error_message"] is None
    assert ready["features"]["chapters"] == YOUTUBE_LONG_FORM_FEATURES["chapters"]
    assert ready["features"]["tags"] == ["editing", "storytime"]
    assert len(ready["features"]["thumbnail_briefs"]) == 3

    listing = test_client.get(f"/api/v1/clips/{clip.id}/adaptations")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [adaptation_id]


def test_regenerate_returns_cached_ready_row_without_regeneration(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    stub_rendering(monkeypatch)
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    calls = {"count": 0}

    def counting_generate(clip, platform, surface, segments, chat_context=None, **kwargs):
        calls["count"] += 1
        return llm.AdaptationFeatures(
            platform=platform,
            surface=surface,
            thumbnail_briefs=[
                {"frame_timestamp": 3.0, "overlay_text": f"thumb {i}"} for i in range(3)
            ],
            platform_hooks=["hook"],
        )

    monkeypatch.setattr(llm, "generate_adaptation_features", counting_generate)

    first = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/youtube/SHORTS")
    adaptation_id = first.json()["id"]
    assert first.json()["status"] == "PENDING"
    ready = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert ready["status"] == "READY"

    second = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/youtube/SHORTS")

    assert second.status_code == 200
    assert second.json()["id"] == adaptation_id
    assert second.json()["status"] == "READY"
    assert calls["count"] == 1


def test_pending_request_returns_cached_pending_row(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    _minds_env: None,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    monkeypatch.setattr(llm, "generate_adaptation_features", lambda *a, **k: pytest.fail("generation ran"))

    with get_session_factory()() as db:
        row = ClipAdaptation(clip_id=clip.id, platform="x", surface="POST")
        db.add(row)
        db.commit()
        row_id = row.id

    test_client.post(f"/api/v1/clips/{clip.id}/adaptations/x/POST")
    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/x/POST")

    assert res.status_code == 200
    assert res.json()["id"] == row_id
    assert res.json()["status"] == "PENDING"


def test_minds_failure_fails_adaptation_with_error_message(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    stub_features(monkeypatch, error=minds.MindsError("builder api down"))

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/POST")

    assert res.status_code == 202
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "FAILED"
    assert "builder api down" in detail["error_message"]
    assert detail["features"] is None


def test_failed_adaptation_can_be_retried(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    stub_rendering(monkeypatch)
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    stub_features(monkeypatch, error=minds.MindsError("builder api down"))

    first = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/POST")
    adaptation_id = first.json()["id"]

    stub_features(
        monkeypatch,
        features={
            "overlay_spec": [{"text": "boom", "placement": "center", "style": "bold"}],
            "caption_style": "bold white",
            "stickers": [{"emoji": "🔥", "placement": "top-right"}],
            "pinned_comment": "First!",
        },
    )
    retry = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/POST")

    assert retry.status_code == 202
    assert retry.json()["id"] == adaptation_id
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "READY"
    assert detail["features"]["pinned_comment"] == "First!"
    assert detail["error_message"] is None
