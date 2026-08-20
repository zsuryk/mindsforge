from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text

from app.core.config import BACKEND_DIR


@pytest.fixture()
def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def test_init_db_migrates_pre_existing_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "legacy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from app.core.config import get_settings

    get_settings.cache_clear()

    # Build a legacy DB at the initial baseline (schema without transcript_segments).
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_config, "f33fde83ba9c")

    from app.db.base import get_engine, get_session_factory

    get_engine.cache_clear()
    with get_session_factory()() as db:
        db.execute(
            text(
                "INSERT INTO jobs (id, title, source_url, status, created_at, updated_at) "
                "VALUES ('legacy-job', 'Legacy job', 'https://example.com/video', 'PENDING', "
                "datetime('now'), datetime('now'))"
            )
        )
        db.commit()

    # Startup migration brings the legacy DB to head and keeps existing rows.
    from app.db.base import init_db

    init_db()

    assert "transcript_segments" in {c["name"] for c in inspect(get_engine()).get_columns("jobs")}

    from app.models import clip, experiment, job  # noqa: F401
    from sqlalchemy import select

    from app.models.job import Job

    with get_session_factory()() as db:
        row = db.get(Job, "legacy-job")
        assert row is not None
        assert row.title == "Legacy job"
        assert row.transcript_segments is None


def test_0006_adds_ab_data_source_column_with_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "ab-source.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from app.core.config import get_settings

    get_settings.cache_clear()

    # Build a DB at the pre-0006 head (0007) and insert an experiment.
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_config, "d8e9f0a1b2c3")

    from app.db.base import get_engine, get_session_factory

    get_engine.cache_clear()
    with get_session_factory()() as db:
        db.execute(
            text(
                "INSERT INTO jobs (id, title, status, created_at, updated_at) "
                "VALUES ('j1', 'Job', 'COMPLETED', datetime('now'), datetime('now'))"
            )
        )
        db.execute(
            text(
                "INSERT INTO clips (id, job_id, title, start_time, end_time, "
                "transcript_text, file_path, created_at) "
                "VALUES ('clip-1', 'j1', 'Clip', 0, 30, 't', '/tmp/c.mp4', datetime('now'))"
            )
        )
        db.execute(
            text(
                "INSERT INTO ab_experiments (id, clip_id, platform, status, "
                "variants, created_at) "
                "VALUES ('exp-1', 'clip-1', 'youtube_shorts', 'ACTIVE', '[]', datetime('now'))"
            )
        )
        db.commit()

    # Upgrade to head: the column appears with the SIMULATED default.
    command.upgrade(alembic_config, "head")

    columns = {c["name"] for c in inspect(get_engine()).get_columns("ab_experiments")}
    assert "data_source" in columns
    with get_session_factory()() as db:
        source = db.execute(
            text("SELECT data_source FROM ab_experiments WHERE id = 'exp-1'")
        ).scalar_one()
        assert source == "SIMULATED"

    # Downgrade back: the column is dropped.
    command.downgrade(alembic_config, "d8e9f0a1b2c3")

    columns = {c["name"] for c in inspect(get_engine()).get_columns("ab_experiments")}
    assert "data_source" not in columns
