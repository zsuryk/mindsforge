import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import minds


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "mindsforge-backend"
    assert body["minds"] in ("ok", "down", "unconfigured")
    assert body["timestamp"]


@pytest.mark.parametrize("status", ["ok", "down", "unconfigured"])
def test_health_reports_minds_status(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    monkeypatch.setattr(minds, "check_connection", lambda: status)
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["minds"] == status


def test_health_cors_header(client: TestClient) -> None:
    res = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"