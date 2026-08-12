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
