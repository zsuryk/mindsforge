from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import get_engine
from app.models.job import Job, JobStatus


def test_submit_job_by_url_returns_202_and_persists(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )

    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "PENDING"
    assert body["message"]
    job_id = body["job_id"]
    assert job_id

    detail = test_client.get(f"/api/v1/jobs/{job_id}")
    assert detail.status_code == 200
    job = detail.json()
    assert job["id"] == job_id
    assert job["title"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert job["status"] == "PENDING"
    assert job["source_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert job["file_path"] is None
    assert job["duration_seconds"] is None
    assert job["error_message"] is None
    assert job["created_at"]
    assert job["updated_at"]


def test_submit_job_with_title_uses_provided_title(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client

    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/video.mp4", "title": "My cool video"},
    )

    assert res.status_code == 202
    job_id = res.json()["job_id"]
    detail = test_client.get(f"/api/v1/jobs/{job_id}")
    assert detail.json()["title"] == "My cool video"


def test_submit_job_by_file_upload_persists_file(
    client: tuple[TestClient, Path],
) -> None:
    test_client, media_dir = client
    content = b"fake video bytes"

    res = test_client.post(
        "/api/v1/jobs/process",
        files={"file": ("my-video.mp4", content, "video/mp4")},
    )

    assert res.status_code == 202
    job_id = res.json()["job_id"]
    detail = test_client.get(f"/api/v1/jobs/{job_id}")
    job = detail.json()
    assert job["status"] == "PENDING"
    assert job["source_url"] is None
    assert job["title"] == "my-video.mp4"

    saved_path = Path(job["file_path"])
    assert saved_path.is_relative_to(media_dir / "media" / "uploads")
    assert saved_path.read_bytes() == content


def test_submit_without_source_url_or_file_is_rejected(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    res = test_client.post("/api/v1/jobs/process", data={})
    assert res.status_code == 422


def test_submit_with_both_url_and_file_is_rejected(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/video.mp4"},
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    assert res.status_code == 422


def test_submit_with_invalid_url_is_rejected(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "not-a-url"},
    )
    assert res.status_code == 422


def test_duplicate_in_progress_url_is_rejected(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    url = "https://example.com/same-video.mp4"

    first = test_client.post("/api/v1/jobs/process", data={"source_url": url})
    assert first.status_code == 202

    second = test_client.post("/api/v1/jobs/process", data={"source_url": url})
    assert second.status_code == 409


def test_completed_url_can_be_submitted_again(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    url = "https://example.com/rerun-video.mp4"

    first = test_client.post("/api/v1/jobs/process", data={"source_url": url})
    job_id = first.json()["job_id"]
    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with session_factory() as db:
        job = db.get(Job, job_id)
        job.status = JobStatus.COMPLETED
        db.commit()

    second = test_client.post("/api/v1/jobs/process", data={"source_url": url})
    assert second.status_code == 202


def test_get_unknown_job_returns_404(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.get("/api/v1/jobs/does-not-exist")
    assert res.status_code == 404


def test_list_jobs_returns_newest_first(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client

    first = test_client.post(
        "/api/v1/jobs/process", data={"source_url": "https://example.com/first.mp4"}
    )
    second = test_client.post(
        "/api/v1/jobs/process", data={"source_url": "https://example.com/second.mp4"}
    )
    assert first.status_code == 202 and second.status_code == 202

    res = test_client.get("/api/v1/jobs")
    assert res.status_code == 200
    jobs = res.json()
    assert [job["id"] for job in jobs] == [
        second.json()["job_id"],
        first.json()["job_id"],
    ]
    assert all(job["status"] == "PENDING" for job in jobs)


def test_manually_submitted_job_survives_backend_restart(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/durable.mp4"},
    )
    job_id = res.json()["job_id"]

    get_settings.cache_clear()
    get_engine.cache_clear()

    from app.main import app

    with TestClient(app) as restarted:
        detail = restarted.get(f"/api/v1/jobs/{job_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "PENDING"


def test_delete_job_removes_job(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/delete-me.mp4"},
    )
    job_id = res.json()["job_id"]

    deleted = test_client.delete(f"/api/v1/jobs/{job_id}")
    assert deleted.status_code == 204

    assert test_client.get(f"/api/v1/jobs/{job_id}").status_code == 404


def test_delete_unknown_job_returns_404(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    assert test_client.delete("/api/v1/jobs/does-not-exist").status_code == 404


def test_delete_job_cascades_to_clips_and_experiments(
    client: tuple[TestClient, Path],
) -> None:
    from app.models.adaptation import AdaptationStatus, ClipAdaptation, AdaptationSurface
    from app.models.clip import Clip
    from app.models.experiment import AbExperiment, AbExperimentStatus

    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/cascade.mp4"},
    )
    job_id = res.json()["job_id"]

    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with session_factory() as db:
        job = db.get(Job, job_id)
        clip = Clip(
            id="clip-1",
            job_id=job.id,
            title="clip",
            start_time=0.0,
            end_time=1.0,
            transcript_text="t",
            file_path="/tmp/c.mp4",
        )
        db.add(clip)
        db.flush()
        db.add(
            AbExperiment(
                clip_id=clip.id,
                platform="tiktok",
                status=AbExperimentStatus.ACTIVE,
                variants=[{"variant_id": "v1", "title": "A", "ctr": 0.0, "views": 0}],
            )
        )
        db.add(
            ClipAdaptation(
                clip_id=clip.id,
                platform="tiktok",
                surface=AdaptationSurface.POST,
                status=AdaptationStatus.PENDING,
            )
        )
        db.commit()

    assert test_client.delete(f"/api/v1/jobs/{job_id}").status_code == 204

    with session_factory() as db:
        assert db.get(Job, job_id) is None
        assert db.get(Clip, "clip-1") is None


def test_retry_failed_job_resets_to_pending(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/retry.mp4"},
    )
    job_id = res.json()["job_id"]

    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with session_factory() as db:
        job = db.get(Job, job_id)
        job.status = JobStatus.FAILED
        job.error_message = "network down"
        db.commit()

    retried = test_client.post(f"/api/v1/jobs/{job_id}/retry")
    assert retried.status_code == 202

    detail = test_client.get(f"/api/v1/jobs/{job_id}").json()
    assert detail["status"] == "PENDING"
    assert detail["error_message"] is None


def test_retry_clears_existing_clips(client: tuple[TestClient, Path]) -> None:
    from app.models.clip import Clip

    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/retry-clips.mp4"},
    )
    job_id = res.json()["job_id"]

    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with session_factory() as db:
        job = db.get(Job, job_id)
        job.status = JobStatus.FAILED
        db.add(
            Clip(
                id="clip-9",
                job_id=job.id,
                title="old",
                start_time=0.0,
                end_time=1.0,
                transcript_text="t",
                file_path="/tmp/old.mp4",
            )
        )
        db.commit()

    assert test_client.post(f"/api/v1/jobs/{job_id}/retry").status_code == 202

    assert test_client.get(f"/api/v1/jobs/{job_id}/clips").json() == []


def test_retry_in_progress_job_returns_409(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/in-flight.mp4"},
    )
    job_id = res.json()["job_id"]

    assert test_client.post(f"/api/v1/jobs/{job_id}/retry").status_code == 409


def test_retry_unknown_job_returns_404(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    assert test_client.post("/api/v1/jobs/does-not-exist/retry").status_code == 404


def test_orphaned_in_progress_jobs_are_failed_on_restart(
    client: tuple[TestClient, Path],
    monkeypatch,
) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/jobs/process",
        data={"source_url": "https://example.com/orphan.mp4"},
    )
    job_id = res.json()["job_id"]

    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "true")
    get_settings.cache_clear()
    get_engine.cache_clear()

    from app.main import app

    with TestClient(app) as restarted:
        detail = restarted.get(f"/api/v1/jobs/{job_id}").json()
        assert detail["status"] == "FAILED"
        assert "interrupted" in detail["error_message"]