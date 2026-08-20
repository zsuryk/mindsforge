from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.adaptation import ClipAdaptation
from app.models.clip import Clip
from app.models.job import Job
from app.services import adaptations, minds

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
        clip, platform, surface, segments, memory_context=None, conversation_alias=None
    ):
        if error is not None:
            raise error
        return minds.AdaptationFeatures(
            platform=platform, surface=surface, **(features or {})
        )

    monkeypatch.setattr(minds, "generate_adaptation_features", generate)


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

    def counting_generate(clip, platform, surface, segments, memory_context=None, **kwargs):
        calls["count"] += 1
        return minds.AdaptationFeatures(
            platform=platform,
            surface=surface,
            thumbnail_briefs=[
                {"frame_timestamp": 3.0, "overlay_text": f"thumb {i}"} for i in range(3)
            ],
            platform_hooks=["hook"],
        )

    monkeypatch.setattr(minds, "generate_adaptation_features", counting_generate)

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
    monkeypatch.setattr(minds, "generate_adaptation_features", lambda *a, **k: pytest.fail("generation ran"))

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


def test_each_adaptation_attempt_uses_fresh_conversation_alias(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    stub_rendering(monkeypatch)
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    aliases: list[str] = []

    def capturing_generate(clip, platform, surface, segments, memory_context=None, **kwargs):
        aliases.append(kwargs.get("conversation_alias"))
        features = (
            {
                "thumbnail_briefs": [
                    {"frame_timestamp": 3.0, "overlay_text": f"thumb {i}"} for i in range(3)
                ],
                "platform_hooks": ["hook"],
            }
            if platform == "youtube"
            else {"caption": "hot take", "hashtags": ["#hot"]}
        )
        return minds.AdaptationFeatures(platform=platform, surface=surface, **features)

    monkeypatch.setattr(minds, "generate_adaptation_features", capturing_generate)

    first = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/youtube/SHORTS")
    assert first.status_code == 202
    first_id = first.json()["id"]
    ready = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{first_id}").json()
    assert ready["status"] == "READY"

    second = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/x/POST")
    assert second.status_code == 202
    second_id = second.json()["id"]
    ready = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{second_id}").json()
    assert ready["status"] == "READY"

    assert len(aliases) == 2
    assert aliases[0] != aliases[1]
    for alias in aliases:
        assert alias is not None and alias.startswith(f"{minds.MESSAGING_ALIAS}-")
        assert len(alias) <= 64, "Builder API rejects aliases longer than 64 chars"


def test_generate_adaptation_404s_for_unknown_clip(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    res = test_client.post("/api/v1/clips/missing/adaptations/youtube/SHORTS")
    assert res.status_code == 404


def test_generate_adaptation_rejects_invalid_surface_for_platform(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/youtube/POST")
    assert res.status_code == 422
    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/LONG_FORM")
    assert res.status_code == 422


def test_adaptation_detail_404s_for_wrong_clip(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    stub_features(monkeypatch, features={"caption": "x", "hashtags": ["#x"]})
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        other = make_clip(db, tmp_path, title="Other clip")

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/x/POST")
    adaptation_id = res.json()["id"]

    assert (
        test_client.get(f"/api/v1/clips/{other.id}/adaptations/{adaptation_id}").status_code == 404
    )


def test_success_appends_adaptation_history_to_minds_memory(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    _minds_env: None,
) -> None:
    test_client, tmp_path = client
    stub_rendering(monkeypatch)
    stub_features(
        monkeypatch,
        features={
            "overlay_spec": [{"text": "boom", "placement": "center", "style": "bold"}],
            "caption_style": "bold white",
            "stickers": [{"emoji": "🔥", "placement": "top-right"}],
            "pinned_comment": "First!",
        },
    )
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: {"adaptation_history": [{"adaptation_id": "older"}]},
    )
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: captured.update(agent_id=agent_id, key=key, value=value)
        or True,
    )
    monkeypatch.setattr(minds, "notify_mind", lambda text: None)

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/POST")
    adaptation_id = res.json()["id"]

    assert captured["agent_id"] == "agent-1"
    assert captured["key"] == "adaptation_history"
    history = captured["value"]
    assert isinstance(history, list) and len(history) == 2
    assert history[0]["adaptation_id"] == "older"
    record = history[1]
    assert record["adaptation_id"] == adaptation_id
    assert record["clip_id"] == clip.id
    assert record["platform"] == "tiktok"
    assert record["surface"] == "POST"
    assert record["features"]["pinned_comment"] == "First!"


def test_success_without_minds_persists_features_locally(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    stub_features(monkeypatch, features={"caption": "short", "hashtags": ["#x"]})
    stub_rendering(monkeypatch)
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/x/POST")
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "READY"


def test_unconfigured_minds_fails_adaptation(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "")
    monkeypatch.setenv("MINDS_AGENT_ID", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/youtube/SHORTS")
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "FAILED"
    assert "MINDS" in detail["error_message"]


def test_asset_rendering_failure_fails_adaptation(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    stub_features(monkeypatch, features=YOUTUBE_LONG_FORM_FEATURES)

    from app.services import media

    def broken_extract(source, dest, timestamp):
        raise media.MediaError("ffmpeg failed")

    monkeypatch.setattr(media, "extract_frame_at_timestamp", broken_extract)
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        clip.job.file_path = clip.file_path
        db.commit()

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/youtube/LONG_FORM")
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "FAILED"
    assert "ffmpeg failed" in detail["error_message"]
    assert detail["assets"] is None


def test_excess_overlay_specs_fail_adaptation_instead_of_silently_dropping(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    # make_clip's clip window [2.0, 32.0] spans exactly 2 segments
    stub_features(
        monkeypatch,
        features={
            "overlay_spec": [
                {"text": "one", "placement": "top", "style": "bold"},
                {"text": "two", "placement": "center", "style": "bold"},
                {"text": "three", "placement": "bottom", "style": "italic"},
            ],
            "caption_style": "bold white",
            "stickers": [{"emoji": "🔥", "placement": "top-right"}],
            "pinned_comment": "First!",
        },
    )
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        clip.job.file_path = clip.file_path
        db.commit()

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/POST")
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "FAILED"
    assert "3 overlay specs" in detail["error_message"]
    assert "2 segments" in detail["error_message"]


def test_feature_manifest_validator_rejects_impossible_pairings() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Unsupported adaptation target"):
        minds.AdaptationFeatures(
            platform="tiktok",
            surface="LONG_FORM",
            chapters=[{"title": "x", "timestamp": 1.0}],
            tags=["t"],
            poll={"question": "q", "options": ["a"]},
            quiz=[{"question": "q", "answer": "a"}],
            thumbnail_briefs=[{"frame_timestamp": 1.0, "overlay_text": "x"}],
            shorts_link="s",
        )
    with pytest.raises(ValidationError, match="Unsupported adaptation target"):
        minds.AdaptationFeatures(
            platform="youtube",
            surface="POST",
            caption="x",
            hashtags=["#x"],
        )


def test_feature_manifest_validator_requires_all_mandatory_features() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="youtube SHORTS requires platform_hooks"):
        minds.AdaptationFeatures(
            platform="youtube",
            surface="SHORTS",
            thumbnail_briefs=[
                {"frame_timestamp": 1.0, "overlay_text": "x"} for _ in range(3)
            ],
        )
    with pytest.raises(ValidationError, match="youtube SHORTS requires exactly 3 thumbnail_briefs"):
        minds.AdaptationFeatures(
            platform="youtube",
            surface="SHORTS",
            thumbnail_briefs=[{"frame_timestamp": 1.0, "overlay_text": "x"}],
            platform_hooks=["h"],
        )
    with pytest.raises(ValidationError, match="youtube LONG_FORM requires shorts_link"):
        minds.AdaptationFeatures(
            platform="youtube",
            surface="LONG_FORM",
            chapters=[{"title": "x", "timestamp": 1.0}],
            tags=["t"],
            poll={"question": "q", "options": ["a"]},
            quiz=[{"question": "q", "answer": "a"}],
            thumbnail_briefs=[
                {"frame_timestamp": 1.0, "overlay_text": "x"} for _ in range(3)
            ],
        )


def test_concurrent_generate_requests_converge_on_cached_row(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    real_commit = Session.commit

    def losing_commit(self):
        # Simulate the losing side of a race: the winner's row appears
        # between our read (no row) and our insert, so the unique constraint
        # rejects our insert.
        with get_session_factory()() as other:
            other.add(ClipAdaptation(clip_id=clip.id, platform="x", surface="POST"))
            real_commit(other)
        raise IntegrityError(
            "INSERT INTO clip_adaptations ...",
            {},
            Exception(
                "UNIQUE constraint failed: "
                "clip_adaptations.clip_id, clip_adaptations.platform, "
                "clip_adaptations.surface"
            ),
        )

    monkeypatch.setattr(Session, "commit", losing_commit)
    try:
        res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/x/POST")
    finally:
        monkeypatch.undo()

    assert res.status_code == 200
    body = res.json()
    assert body["platform"] == "x"
    assert body["surface"] == "POST"
    assert body["status"] in ("PENDING", "GENERATING", "READY", "FAILED")

    with get_session_factory()() as db:
        rows = db.scalars(
            select(ClipAdaptation).where(ClipAdaptation.clip_id == clip.id)
        ).all()
        assert len(rows) == 1
        assert rows[0].id == body["id"]


def test_memory_history_written_only_after_row_is_ready(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    _minds_env: None,
) -> None:
    test_client, tmp_path = client
    stub_rendering(monkeypatch)
    stub_features(
        monkeypatch,
        features={
            "overlay_spec": [{"text": "boom", "placement": "center", "style": "bold"}],
            "caption_style": "bold white",
            "stickers": [{"emoji": "🔥", "placement": "top-right"}],
            "pinned_comment": "First!",
        },
    )
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    statuses_at_fetch: list[str] = []

    def capturing_fetch(agent_id):
        with get_session_factory()() as db:
            row = db.scalar(
                select(ClipAdaptation).where(ClipAdaptation.clip_id == clip.id)
            )
            statuses_at_fetch.append(row.status.value if row else None)
        return {"adaptation_history": []}

    monkeypatch.setattr(minds, "fetch_memory", capturing_fetch)
    monkeypatch.setattr(minds, "update_memory", lambda agent_id, key, value: True)
    monkeypatch.setattr(minds, "notify_mind", lambda text: None)

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/POST")
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "READY"

    assert statuses_at_fetch == ["GENERATING", "READY"]


def test_adaptation_read_prompt_carries_trend_block_when_trend_data_exists(
    monkeypatch: pytest.MonkeyPatch,
    _minds_env: None,
) -> None:
    from datetime import UTC, datetime, timedelta

    recent = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: {
            "trend_research": [
                {
                    "query": "fitness shorts",
                    "platform": "youtube",
                    "results": [
                        {"title": "Best Fitness Shorts", "url": "https://example.com", "content": "content"}
                    ],
                    "researched_at": recent,
                }
            ]
        },
    )

    context = adaptations._memory_context(get_settings())

    assert context is not None
    assert "Trending research (last 7 days):" in context
    assert "fitness shorts" in context
    # The raw trend_research dump is excluded from the adaptation context —
    # the curated block is the only trend signal, so stale entries can never
    # bypass the 7-day bound or reach the prompt twice.
    assert "\ntrend_research:" not in context
    prompt = minds._build_adaptation_read_prompt(
        {"id": "c1", "title": "t", "start_time": 0, "end_time": 10, "transcript": "x"},
        "youtube",
        "LONG_FORM",
        [{"start": 0, "end": 5, "text": "hi"}],
        context,
    )
    assert "Trending research (last 7 days):" in prompt


def test_adaptation_memory_context_has_no_trend_block_without_trend_data(
    monkeypatch: pytest.MonkeyPatch,
    _minds_env: None,
) -> None:
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {"brand_voice": "bold"})

    context = adaptations._memory_context(get_settings())

    assert context is not None
    assert "Trending research" not in context


def test_ready_adaptation_posts_notification_with_feature_summary(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    _minds_env: None,
) -> None:
    test_client, tmp_path = client
    stub_rendering(monkeypatch)
    stub_features(
        monkeypatch,
        features={
            "overlay_spec": [{"text": "boom", "placement": "center", "style": "bold"}],
            "caption_style": "bold white",
            "stickers": [{"emoji": "🔥", "placement": "top-right"}],
            "pinned_comment": "First!",
        },
    )
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    notifications: list[str] = []
    monkeypatch.setattr(minds, "notify_mind", notifications.append)

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/POST")
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "READY"

    assert len(notifications) == 1
    text = notifications[0]
    assert text.startswith("Adaptation ready: 'Adaptation clip' for tiktok/POST — ")
    assert "overlays" in text
    assert "captions" in text
    assert "stickers" in text
    assert "pinned comment" in text


def test_ready_adaptation_notification_includes_thumbnail_count(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    _minds_env: None,
) -> None:
    test_client, tmp_path = client
    stub_rendering(monkeypatch)
    stub_features(
        monkeypatch,
        features={
            "thumbnail_briefs": [
                {"frame_timestamp": 3.0, "overlay_text": f"thumb {i}"} for i in range(3)
            ],
            "platform_hooks": ["hook"],
        },
    )
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    notifications: list[str] = []
    monkeypatch.setattr(minds, "notify_mind", notifications.append)

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/youtube/SHORTS")
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()
    assert detail["status"] == "READY"

    assert len(notifications) == 1
    assert "3 thumbnail briefs, platform hooks." in notifications[0]


def test_notification_failure_leaves_adaptation_ready(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    stub_rendering(monkeypatch)
    stub_features(
        monkeypatch,
        features={
            "overlay_spec": [{"text": "boom", "placement": "center", "style": "bold"}],
            "caption_style": "bold white",
            "stickers": [{"emoji": "🔥", "placement": "top-right"}],
            "pinned_comment": "First!",
        },
    )
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    monkeypatch.setattr(
        minds,
        "post_chat_notification",
        lambda text: (_ for _ in ()).throw(minds.MindsError("builder api down")),
    )

    res = test_client.post(f"/api/v1/clips/{clip.id}/adaptations/tiktok/POST")
    adaptation_id = res.json()["id"]
    detail = test_client.get(f"/api/v1/clips/{clip.id}/adaptations/{adaptation_id}").json()

    assert detail["status"] == "READY"
    assert detail["error_message"] is None