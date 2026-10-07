from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import llm


@pytest.fixture
def health_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'health.db'}")
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    from app.core.config import get_settings
    from app.db.base import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
    get_engine.cache_clear()


def test_health(health_client: TestClient) -> None:
    res = health_client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "mindsforge-backend"
    assert body["llm"] in ("ok", "down", "unconfigured")
    assert body["timestamp"]


def test_health_reports_llm_ok_when_the_probe_answers(
    health_client: TestClient, configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    res = health_client.get("/api/v1/health")
    assert res.json()["llm"] == "ok"
    assert llm_http.urls == ["http://localhost:11434/v1/models"]


def test_health_reports_llm_down_when_the_probe_fails(
    health_client: TestClient, configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.models_status_is(503)
    assert health_client.get("/api/v1/health").json()["llm"] == "down"


def test_health_reports_llm_unconfigured_without_a_base_url(
    health_client: TestClient, configure_llm: Any, llm_http: Any
) -> None:
    configure_llm(base_url="")
    res = health_client.get("/api/v1/health")
    assert res.json()["llm"] == "unconfigured"
    assert llm_http.requests == []


def test_health_reports_llm_down_on_a_transport_error(
    health_client: TestClient, configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.fail_with(httpx.ConnectError("connection refused"))
    assert health_client.get("/api/v1/health").json()["llm"] == "down"


def test_health_cors_header(health_client: TestClient) -> None:
    res = health_client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
