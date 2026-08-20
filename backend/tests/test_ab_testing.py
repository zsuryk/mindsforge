import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import get_session_factory
from app.models.activity import MindActivity
from app.models.clip import Clip
from app.models.experiment import AbExperiment, AbExperimentStatus
from app.models.job import Job
from app.services import ab_testing, minds


def make_clip(db, tmp_path: Path, title: str = "My clip") -> Clip:
    job = Job(id=str(uuid4()), title="Job 1")
    db.add(job)
    thumb = tmp_path / "media" / "clips" / "job-1" / "thumb.png"
    thumb.parent.mkdir(parents=True, exist_ok=True)
    thumb.write_bytes(b"png")
    clip = Clip(
        id=str(uuid4()),
        job_id=job.id,
        title=title,
        start_time=0.0,
        end_time=30.0,
        transcript_text="some transcript",
        file_path=str(thumb),
        thumbnail_path=str(thumb),
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def add_experiment(db, *, variants, status=AbExperimentStatus.ACTIVE, **kwargs) -> AbExperiment:
    experiment = AbExperiment(
        platform="youtube_shorts",
        status=status,
        variants=variants,
        **kwargs,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def stub_winner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    variant_id: str | None = None,
    reasoning: str = "Hook A held viewers longer; reuse this formula.",
) -> None:
    def decide(platform, variants, transcript, memory_context=None):
        picked = variant_id if variant_id is not None else variants[0]["variant_id"]
        return minds.ExperimentVerdict(winning_variant_id=picked, reasoning=reasoning)

    monkeypatch.setattr(minds, "decide_experiment_winner", decide)


@pytest.fixture()
def _minds_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_start_ab_test_creates_active_experiment_with_variant_thumbs(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    res = test_client.post(
        "/api/v1/ab-tests/start",
        json={
            "clip_id": clip.id,
            "platform": "tiktok",
            "titles": ["First title", "Second title", "Third title"],
        },
    )

    assert res.status_code == 201
    body = res.json()
    assert body["clip_id"] == clip.id
    assert body["clip_title"] == "My clip"
    assert body["platform"] == "tiktok"
    assert body["status"] == "ACTIVE"
    assert body["variant_kind"] == "TITLE"
    assert body["error_message"] is None
    assert body["winning_variant_id"] is None
    assert body["learned_insight"] is None
    assert body["concluded_at"] is None
    assert len(body["variants"]) == 3
    for variant in body["variants"]:
        assert variant["variant_id"]
        assert variant["views"] == 0
        assert variant["ctr"] == 0.0
        assert variant["thumbnail_url"] == "/media/clips/job-1/thumb.png"

    with get_session_factory()() as db:
        stored = db.get(AbExperiment, body["id"])
        assert stored is not None
        assert stored.status == AbExperimentStatus.ACTIVE
        assert stored.clip_id == clip.id


def test_start_ab_test_404s_for_unknown_clip(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/ab-tests/start",
        json={"clip_id": "missing", "platform": "tiktok", "titles": ["a", "b"]},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Clip not found"


def test_start_ab_test_rejects_unknown_platform(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    res = test_client.post(
        "/api/v1/ab-tests/start",
        json={"clip_id": clip.id, "platform": "myspace", "titles": ["a", "b"]},
    )
    assert res.status_code == 422


def test_start_ab_test_requires_two_distinct_titles(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
    res = test_client.post(
        "/api/v1/ab-tests/start",
        json={"clip_id": clip.id, "platform": "tiktok", "titles": ["same", "same"]},
    )
    assert res.status_code == 422
    assert "two distinct variant titles" in res.json()["detail"]

    single = test_client.post(
        "/api/v1/ab-tests/start",
        json={"clip_id": clip.id, "platform": "tiktok", "titles": ["only one"]},
    )
    assert single.status_code == 422


def test_start_ab_test_with_thumbnail_variant_kind_uses_per_variant_thumbs(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    thumbnails = [
        str(tmp_path / "media" / "adaptations" / "adapt-1" / "thumb_1.png"),
        str(tmp_path / "media" / "adaptations" / "adapt-1" / "thumb_2.png"),
        str(tmp_path / "media" / "adaptations" / "adapt-1" / "thumb_3.png"),
    ]
    res = test_client.post(
        "/api/v1/ab-tests/start",
        json={
            "clip_id": clip.id,
            "platform": "youtube_shorts",
            "variant_kind": "THUMBNAIL",
            "titles": [],
            "thumbnail_paths": thumbnails,
        },
    )

    assert res.status_code == 201
    body = res.json()
    assert body["variant_kind"] == "THUMBNAIL"
    assert len(body["variants"]) == 3
    for index, variant in enumerate(body["variants"]):
        assert variant["thumbnail_url"] == f"/media/adaptations/adapt-1/thumb_{index + 1}.png"
        assert variant["title"] == f"Thumbnail {index + 1}"


def test_start_ab_test_thumbnail_kind_requires_two_distinct_thumbnails(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    res = test_client.post(
        "/api/v1/ab-tests/start",
        json={
            "clip_id": clip.id,
            "platform": "youtube_shorts",
            "variant_kind": "THUMBNAIL",
            "titles": [],
            "thumbnail_paths": ["/media/adaptations/adapt-1/thumb_1.png"],
        },
    )
    assert res.status_code == 422
    assert "two distinct thumbnail variants" in res.json()["detail"]


def test_active_endpoint_returns_active_and_recently_concluded_newest_first(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    now = datetime.now(timezone.utc)
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        active = add_experiment(
            db,
            clip_id=clip.id,
            variants=[{"variant_id": "v1", "title": "A", "ctr": 1.0, "views": 50}],
            created_at=now - timedelta(hours=1),
        )
        concluded = add_experiment(
            db,
            clip_id=clip.id,
            variants=[{"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 100}],
            status=AbExperimentStatus.CONCLUDED,
            winning_variant_id="v2",
            learned_insight="B won",
            concluded_at=now,
            created_at=now - timedelta(hours=2),
        )
        stale = add_experiment(
            db,
            clip_id=clip.id,
            variants=[{"variant_id": "v4", "title": "D", "ctr": 1.0, "views": 10}],
            status=AbExperimentStatus.CONCLUDED,
            winning_variant_id="v4",
            learned_insight="old",
            concluded_at=now - timedelta(days=30),
            created_at=now - timedelta(days=31),
        )
        failed = add_experiment(
            db,
            clip_id=clip.id,
            variants=[{"variant_id": "v3", "title": "C", "ctr": 1.0, "views": 10}],
            status=AbExperimentStatus.FAILED,
            error_message="builder api down",
            created_at=now - timedelta(days=31),
            concluded_at=now - timedelta(hours=3),
        )

    res = test_client.get("/api/v1/ab-tests/active")

    assert res.status_code == 200
    body = res.json()
    assert body["view_threshold"] == 1000
    ids = [item["id"] for item in body["experiments"]]
    assert ids == [active.id, concluded.id, failed.id]
    assert stale.id not in ids
    concluded_body = body["experiments"][1]
    assert concluded_body["status"] == "CONCLUDED"
    assert concluded_body["winning_variant_id"] == "v2"
    assert concluded_body["learned_insight"] == "B won"
    assert concluded_body["clip_title"] == "My clip"
    failed_body = body["experiments"][2]
    assert failed_body["status"] == "FAILED"
    assert failed_body["error_message"] == "builder api down"


def test_sweep_accumulates_views_and_keeps_experiment_active_below_threshold(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 0.0, "views": 0},
                {"variant_id": "v2", "title": "B", "ctr": 0.0, "views": 0},
            ],
        )

    concluded = ab_testing.refresh_active_experiments(
        rng=random.Random(42), view_threshold=10_000
    )

    assert concluded == []
    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.ACTIVE
        for variant in stored.variants:
            assert variant["views"] > 0
            assert variant["ctr"] >= 0.0
        total = sum(variant["views"] for variant in stored.variants)
        assert total >= 2 * ab_testing.VIEWS_PER_SWEEP_MIN


def test_sweep_concludes_above_threshold_with_mind_decided_winner(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    stub_winner(monkeypatch, variant_id="v1", reasoning="A won because of its hook.")

    concluded = ab_testing.refresh_active_experiments(view_threshold=1000)

    assert [item.id for item in concluded] == [experiment.id]
    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.CONCLUDED
        assert stored.winning_variant_id == "v1"
        assert stored.concluded_at is not None
        assert stored.learned_insight == "A won because of its hook."

    body = test_client.get("/api/v1/ab-tests/active").json()["experiments"][0]
    assert body["status"] == "CONCLUDED"
    assert body["winning_variant_id"] == "v1"
    assert body["concluded_at"] is not None
    assert body["learned_insight"] == "A won because of its hook."


def test_mind_failure_fails_experiment_with_error_message(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    monkeypatch.setattr(
        minds,
        "decide_experiment_winner",
        lambda platform, variants, transcript, memory_context=None: (
            _ for _ in ()
        ).throw(minds.MindsError("builder api down")),
    )

    concluded = ab_testing.refresh_active_experiments(view_threshold=1000)

    assert [item.id for item in concluded] == [experiment.id]
    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.FAILED
        assert stored.winning_variant_id is None
        assert stored.learned_insight is None
        assert "builder api down" in stored.error_message

    body = test_client.get("/api/v1/ab-tests/active").json()
    assert experiment.id in {item["id"] for item in body["experiments"]}
    failed_body = next(
        item for item in body["experiments"] if item["id"] == experiment.id
    )
    assert failed_body["status"] == "FAILED"
    assert "builder api down" in failed_body["error_message"]


def test_unconfigured_minds_fails_experiment_at_conclusion(
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
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    ab_testing.refresh_active_experiments(view_threshold=1000)

    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.FAILED
        assert stored.winning_variant_id is None
        assert "MINDS" in stored.error_message
        assert "not configured" in stored.error_message


def test_mind_picking_unknown_variant_fails_experiment(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    monkeypatch.setattr(
        minds,
        "decide_experiment_winner",
        lambda platform, variants, transcript, memory_context=None: (
            _ for _ in ()
        ).throw(minds.MindsError("Experiment verdict picked unknown variant id 'ghost'")),
    )

    ab_testing.refresh_active_experiments(view_threshold=1000)

    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.FAILED
        assert "unknown variant id" in stored.error_message


def test_unexpected_exception_fails_only_that_experiment(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        first = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )
        second = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v3", "title": "C", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v4", "title": "D", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    def decide(platform, variants, transcript, memory_context=None):
        if variants[0]["variant_id"] == "v1":
            raise RuntimeError("boom in the verdict code")
        return minds.ExperimentVerdict(
            winning_variant_id="v3", reasoning="C won."
        )

    monkeypatch.setattr(minds, "decide_experiment_winner", decide)

    concluded = ab_testing.refresh_active_experiments(view_threshold=1000)

    assert {item.id for item in concluded} == {first.id, second.id}
    with get_session_factory()() as db:
        failed = db.get(AbExperiment, first.id)
        assert failed.status == AbExperimentStatus.FAILED
        assert "boom in the verdict code" in failed.error_message
        winner = db.get(AbExperiment, second.id)
        assert winner.status == AbExperimentStatus.CONCLUDED
        assert winner.winning_variant_id == "v3"
        assert winner.learned_insight == "C won."


def test_winner_prompt_lists_thumbnail_references_and_glossary_terms(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {
                    "variant_id": "v1",
                    "title": "A",
                    "thumbnail_path": "/media/adaptations/adapt-1/thumb_1.png",
                    "ctr": 5.0,
                    "views": 600,
                    "clicks": 30,
                },
                {
                    "variant_id": "v2",
                    "title": "B",
                    "thumbnail_path": "/media/adaptations/adapt-1/thumb_2.png",
                    "ctr": 2.0,
                    "views": 400,
                    "clicks": 8,
                },
            ],
        )

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"response": '{"winning_variant_id": "v1", "reasoning": "A won"}'}

    captured: dict[str, object] = {}

    def fake_message_mind(agent_id, prompt):
        captured["agent_id"] = agent_id
        captured["prompt"] = prompt
        return '{"winning_variant_id": "v1", "reasoning": "A won"}'

    monkeypatch.setattr(minds, "_message_mind", fake_message_mind)
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    monkeypatch.setattr(minds, "notify_mind", lambda text: None)

    ab_testing.refresh_active_experiments(view_threshold=1000)

    assert captured["agent_id"] == "agent-1"
    prompt = captured["prompt"]
    assert isinstance(prompt, str)
    assert "thumbnail: /media/adaptations/adapt-1/thumb_1.png" in prompt
    assert "thumbnail: /media/adaptations/adapt-1/thumb_2.png" in prompt
    assert "experiment analyst" in prompt
    assert "learned insight" in prompt
    assert "A/B testing analyst" not in prompt
    assert "lesson" not in prompt


def test_conclusion_writes_insight_to_minds_memory(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    stub_winner(monkeypatch, variant_id="v1", reasoning="A won; reuse its hook style.")
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: {"ab_test_history": [{"experiment_id": "older"}]},
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: captured.update(agent_id=agent_id, key=key, value=value)
        or True,
    )
    monkeypatch.setattr(minds, "notify_mind", lambda text: None)

    ab_testing.refresh_active_experiments(view_threshold=1000)

    assert captured["agent_id"] == "agent-1"
    assert captured["key"] == "ab_test_history"
    history = captured["value"]
    assert isinstance(history, list) and len(history) == 2
    assert history[0]["experiment_id"] == "older"
    record = history[1]
    assert record["experiment_id"] == experiment.id
    assert record["clip_id"] == clip.id
    assert record["platform"] == "youtube_shorts"
    assert record["winning_variant_id"] == "v1"
    assert record["concluded_at"] is not None
    assert record["learned_insight"] == "A won; reuse its hook style."


def test_memory_write_failure_still_concludes_experiment(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    stub_winner(monkeypatch, variant_id="v1", reasoning="A won.")
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: (_ for _ in ()).throw(minds.MindsError("builder api down")),
    )
    monkeypatch.setattr(minds, "notify_mind", lambda text: None)

    ab_testing.refresh_active_experiments(view_threshold=1000)

    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.CONCLUDED
        assert stored.winning_variant_id == "v1"
        assert stored.learned_insight == "A won."


def test_sweep_skips_concluded_experiments(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[{"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600}],
            status=AbExperimentStatus.CONCLUDED,
            winning_variant_id="v1",
            learned_insight="done",
        )

    ab_testing.refresh_active_experiments(rng=random.Random(1), view_threshold=1)

    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.variants[0]["views"] == 600
        assert stored.learned_insight == "done"


def test_launched_experiment_runs_to_conclusion_via_sweeps(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)

    created = test_client.post(
        "/api/v1/ab-tests/start",
        json={"clip_id": clip.id, "platform": "x", "titles": ["Hot take one", "Hot take two"]},
    )
    assert created.status_code == 201
    experiment_id = created.json()["id"]

    stub_winner(
        monkeypatch,
        reasoning="The debate-style hook out-performed; reuse the formula.",
    )
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: captured.update(value=value) or True,
    )
    monkeypatch.setattr(minds, "notify_mind", lambda text: None)

    rng = random.Random(7)
    sweeps = 0
    status = "ACTIVE"
    while status == "ACTIVE" and sweeps < 200:
        concluded = ab_testing.refresh_active_experiments(rng=rng)
        status = concluded[0].status if concluded else status
        sweeps += 1

    assert status == "CONCLUDED"
    assert sweeps > 1

    body = test_client.get("/api/v1/ab-tests/active").json()["experiments"][0]
    assert body["id"] == experiment_id
    assert body["status"] == "CONCLUDED"
    assert body["winning_variant_id"] in {v["variant_id"] for v in body["variants"]}
    assert body["learned_insight"] is not None
    total_views = sum(v["views"] for v in body["variants"])
    assert total_views >= 1000

    history = captured["value"]
    assert isinstance(history, list) and len(history) == 1
    assert history[0]["experiment_id"] == experiment_id
    assert history[0]["learned_insight"] == body["learned_insight"]


def test_concluded_experiment_posts_notification_with_winner_and_insight(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    stub_winner(monkeypatch, variant_id="v1", reasoning="A won; reuse its hook style.")
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    monkeypatch.setattr(minds, "update_memory", lambda agent_id, key, value: True)
    notifications: list[str] = []
    monkeypatch.setattr(minds, "notify_mind", notifications.append)

    ab_testing.refresh_active_experiments(view_threshold=1000)

    assert len(notifications) == 1
    text = notifications[0]
    assert text.startswith("Experiment concluded on clip 'My clip' (youtube_shorts).")
    assert "Winner: v1" in text
    assert "Learned insight: 'A won; reuse its hook style.'" in text


def test_failed_experiment_posts_notification_with_error(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    monkeypatch.setattr(
        minds,
        "decide_experiment_winner",
        lambda platform, variants, transcript, memory_context=None: (
            _ for _ in ()
        ).throw(minds.MindsError("builder api down")),
    )
    notifications: list[str] = []
    monkeypatch.setattr(minds, "notify_mind", notifications.append)

    ab_testing.refresh_active_experiments(view_threshold=1000)

    assert len(notifications) == 1
    assert notifications[0] == f"Experiment {experiment.id} failed: builder api down."


def test_notification_failure_does_not_change_concluded_experiment(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    stub_winner(monkeypatch, variant_id="v1", reasoning="A won.")
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    monkeypatch.setattr(
        minds,
        "post_chat_notification",
        lambda text: (_ for _ in ()).throw(minds.MindsError("builder api down")),
    )

    ab_testing.refresh_active_experiments(view_threshold=1000)

    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.CONCLUDED
        assert stored.winning_variant_id == "v1"


def test_notification_failure_does_not_change_failed_experiment(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    monkeypatch.setattr(
        minds,
        "decide_experiment_winner",
        lambda platform, variants, transcript, memory_context=None: (
            _ for _ in ()
        ).throw(minds.MindsError("builder api down")),
    )
    monkeypatch.setattr(
        minds,
        "post_chat_notification",
        lambda text: (_ for _ in ()).throw(minds.MindsError("builder api down")),
    )

    ab_testing.refresh_active_experiments(view_threshold=1000)

    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.FAILED
        assert "builder api down" in stored.error_message


def _activity_rows() -> list[MindActivity]:
    with get_session_factory()() as db:
        return db.scalars(
            select(MindActivity).order_by(MindActivity.created_at.asc())
        ).all()


def test_sweep_logs_exactly_one_activity_row_when_no_experiments(
    client: tuple[TestClient, Path],
) -> None:
    ab_testing.refresh_active_experiments(view_threshold=1000)

    rows = _activity_rows()
    assert len(rows) == 1
    assert rows[0].event_type == "experiment-sweep"
    assert rows[0].label.startswith("Simulated sweep: +0 views across 0 variants")


def test_sweep_logs_one_row_for_variant_traffic(
    client: tuple[TestClient, Path],
) -> None:
    _, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 0, "clicks": 0},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 0, "clicks": 0},
            ],
        )

    ab_testing.refresh_active_experiments(
        rng=random.Random(3), view_threshold=1000
    )

    rows = [row for row in _activity_rows() if row.event_type == "experiment-sweep"]
    assert len(rows) == 1
    label = rows[0].label
    assert "views across 2 variants" in label
    assert label.startswith("Simulated sweep: +")


def test_conclusion_logs_activity_row_with_winner(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    stub_winner(monkeypatch, variant_id="v1", reasoning="A won; reuse its hook style.")
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    monkeypatch.setattr(minds, "update_memory", lambda agent_id, key, value: True)
    monkeypatch.setattr(minds, "notify_mind", lambda text: None)

    ab_testing.refresh_active_experiments(view_threshold=1000)

    concluded = [
        row
        for row in _activity_rows()
        if row.event_type == "experiment-concluded"
    ]
    assert len(concluded) == 1
    assert concluded[0].ref_id == experiment.id
    assert concluded[0].label == (
        "Experiment concluded on 'My clip' — winner v1"
    )
    assert concluded[0].detail == {"insight": "A won; reuse its hook style."}


def test_failed_experiment_logs_activity_row(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        experiment = add_experiment(
            db,
            clip_id=clip.id,
            variants=[
                {"variant_id": "v1", "title": "A", "ctr": 5.0, "views": 600, "clicks": 30},
                {"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 400, "clicks": 8},
            ],
        )

    monkeypatch.setattr(
        minds,
        "decide_experiment_winner",
        lambda platform, variants, transcript, memory_context=None: (
            _ for _ in ()
        ).throw(minds.MindsError("builder api down")),
    )
    monkeypatch.setattr(minds, "notify_mind", lambda text: None)

    ab_testing.refresh_active_experiments(view_threshold=1000)

    failed = [row for row in _activity_rows() if row.event_type == "experiment-failed"]
    assert len(failed) == 1
    assert failed[0].ref_id == experiment.id
    assert failed[0].label == f"Experiment {experiment.id} failed: builder api down"
