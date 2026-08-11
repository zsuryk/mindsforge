import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.base import get_session_factory
from app.models.clip import Clip
from app.models.experiment import AbExperiment, AbExperimentStatus
from app.services import ab_testing, minds


def make_clip(db, tmp_path: Path, title: str = "My clip") -> Clip:
    thumb = tmp_path / "media" / "clips" / "job-1" / "thumb.png"
    thumb.parent.mkdir(parents=True, exist_ok=True)
    thumb.write_bytes(b"png")
    clip = Clip(
        id=str(uuid4()),
        job_id="job-1",
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


def test_active_endpoint_returns_active_and_recently_concluded_newest_first(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path)
        active = add_experiment(db, clip_id=clip.id, variants=[{"variant_id": "v1", "title": "A", "ctr": 1.0, "views": 50}])
        concluded = add_experiment(
            db,
            clip_id=clip.id,
            variants=[{"variant_id": "v2", "title": "B", "ctr": 2.0, "views": 100}],
            status=AbExperimentStatus.CONCLUDED,
            winning_variant_id="v2",
            learned_insight="B won",
            concluded_at=datetime.now(timezone.utc),
        )
        stale = add_experiment(
            db,
            clip_id=clip.id,
            variants=[{"variant_id": "v4", "title": "D", "ctr": 1.0, "views": 10}],
            status=AbExperimentStatus.CONCLUDED,
            winning_variant_id="v4",
            learned_insight="old",
            concluded_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        failed = add_experiment(
            db,
            clip_id=clip.id,
            variants=[{"variant_id": "v3", "title": "C", "ctr": 1.0, "views": 10}],
            status=AbExperimentStatus.FAILED,
        )

    res = test_client.get("/api/v1/ab-tests/active")

    assert res.status_code == 200
    body = res.json()
    assert body["view_threshold"] == 1000
    ids = [item["id"] for item in body["experiments"]]
    assert ids == [concluded.id, active.id]
    assert failed.id not in ids
    assert stale.id not in ids
    concluded_body = body["experiments"][0]
    assert concluded_body["status"] == "CONCLUDED"
    assert concluded_body["winning_variant_id"] == "v2"
    assert concluded_body["learned_insight"] == "B won"
    assert concluded_body["clip_title"] == "My clip"


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


def test_sweep_concludes_above_threshold_with_highest_ctr_winner(
    client: tuple[TestClient, Path],
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

    concluded = ab_testing.refresh_active_experiments(view_threshold=1000)

    assert [item.id for item in concluded] == [experiment.id]
    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.CONCLUDED
        assert stored.winning_variant_id == "v1"
        assert stored.concluded_at is not None
        assert stored.learned_insight is not None
        assert stored.learned_insight != ""
        assert "A" in stored.learned_insight
        assert "YouTube Shorts" in stored.learned_insight

    body = test_client.get("/api/v1/ab-tests/active").json()["experiments"][0]
    assert body["status"] == "CONCLUDED"
    assert body["winning_variant_id"] == "v1"
    assert body["concluded_at"] is not None
    assert body["learned_insight"] == stored.learned_insight


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
    assert isinstance(record["learned_insight"], str) and record["learned_insight"]


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

    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: (_ for _ in ()).throw(minds.MindsError("builder api down")),
    )

    ab_testing.refresh_active_experiments(view_threshold=1000)

    with get_session_factory()() as db:
        stored = db.get(AbExperiment, experiment.id)
        assert stored.status == AbExperimentStatus.CONCLUDED
        assert stored.winning_variant_id == "v1"
        assert stored.learned_insight is not None


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

    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: {})
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: captured.update(value=value) or True,
    )

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
