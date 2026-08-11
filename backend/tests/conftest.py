from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.base import get_engine


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    db_path = tmp_path / "test.db"
    media_dir = tmp_path / "media"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("MEDIA_DIR", str(media_dir))
    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "false")
    get_settings.cache_clear()
    get_engine.cache_clear()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client, tmp_path

    get_settings.cache_clear()
    get_engine.cache_clear()