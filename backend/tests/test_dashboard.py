from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.base import get_session_factory
from app.models.clip import Clip
from app.models.experiment import AbExperiment, AbExperimentStatus
from app.models.job import Job
from app.services import ab_testing, llm
from app.services.pipeline import _score_clips


def make_clip(db, *, virality_score: int | None = None) -> Clip:
    job = Job(id=str(uuid4()), title="Job 1")
    db.add(job)
    clip = Clip(
        id=str(uuid4()),
        job_id=job.id,
        title="Clip",
        start_time=0.0,
        end_time=30.0,
        transcript_text="some transcript",
        file_path="/tmp/clip.mp4",
        virality_score=virality_score,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def add_experiment(
    db,
    clip: Clip,
    *,
    status: AbExperimentStatus = AbExperimentStatus.ACTIVE,
    learned_insight: str | None = None,
) -> AbExperiment:
    experiment = AbExperiment(
        clip_id=clip.id,
        platform="youtube_shorts",
        status=status,
        variants=[{"variant_id": "v1", "title": "A", "ctr": 0.0, "views": 0}],
        learned_insight=learned_insight,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def test_dashboard_stats_empty(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.get("/api/v1/dashboard/stats")
    assert res.status_code == 200
    assert res.json() == {
        "total_clips": 0,
        "active_ab_tests": 0,
        "avg_virality": None,
        "total_insights": 0,
    }


def test_dashboard_stats_aggregate_live_counts(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    with get_session_factory()() as db:
        clip = make_clip(db, virality_score=50)
        make_clip(db, virality_score=80)
        make_clip(db)
        add_experiment(db, clip)
        add_experiment(
            db,
            clip,
            status=AbExperimentStatus.CONCLUDED,
            learned_insight="A won",
        )
        add_experiment(db, clip, status=AbExperimentStatus.FAILED)
        add_experiment(db, clip, status=AbExperimentStatus.CONCLUDED)

    res = test_client.get("/api/v1/dashboard/stats")

    assert res.status_code == 200
    body = res.json()
    assert body["total_clips"] == 3
    assert body["active_ab_tests"] == 1
    assert body["avg_virality"] == 65.0
    assert body["total_insights"] == 1


def test_dashboard_stats_avg_virality_is_null_without_scored_clips(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    with get_session_factory()() as db:
        make_clip(db)

    body = test_client.get("/api/v1/dashboard/stats").json()
    assert body["total_clips"] == 1
    assert body["avg_virality"] is None


def test_activity_endpoint_lists_simulated_sweep_and_scoring_rows(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    with get_session_factory()() as db:
        clip = make_clip(db)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(llm, "fetch_memory", lambda: None)
    monkeypatch.setattr(
        llm,
        "generate_clip_metadata",
        lambda transcript, duration_seconds=None, chat_context=None, **kwargs: llm.ClipMetadata(
            virality_score=82,
            suggested_titles=["Title A"],
            platform_hooks={"youtube_shorts": ["s"], "tiktok": ["t"], "x": ["x"]},
        ),
    )

    # A simulated sweep with no active experiments still logs its heartbeat.
    ab_testing.refresh_active_experiments(view_threshold=1000)

    # A scoring pass logs one row per scored clip.
    with get_session_factory()() as db:
        job = db.get(Job, clip.job_id)
        assert job is not None
        _score_clips(db, job, "test-alias")

    body = test_client.get("/api/v1/dashboard/activity?limit=20").json()

    event_types = [row["event_type"] for row in body]
    assert "experiment-sweep" in event_types
    assert event_types.count("experiment-sweep") == 1
    assert event_types.count("clip-scored") == 1
    scored = next(row for row in body if row["event_type"] == "clip-scored")
    assert scored["label"] == "Scored clip 'Clip' — virality 82/100"
    assert scored["ref_id"] == clip.id
