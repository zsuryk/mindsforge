from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import minds


@pytest.fixture()
def _minds_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_memory_returns_agent_id_and_tree(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    memory = {"brand_voice": "bold", "historical_insights": {"tiktok": ["fast pacing"]}}
    monkeypatch.setattr(minds, "fetch_memory", lambda agent_id: memory)

    res = test_client.get("/api/v1/agent/memory")

    assert res.status_code == 200
    assert res.json() == {"agent_id": "agent-1", "memory": memory}


def test_get_memory_passes_configured_agent_id(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    captured: dict[str, str] = {}

    def fake_fetch(agent_id: str) -> dict:
        captured["agent_id"] = agent_id
        return {}

    monkeypatch.setattr(minds, "fetch_memory", fake_fetch)

    res = test_client.get("/api/v1/agent/memory")

    assert res.status_code == 200
    assert captured["agent_id"] == "agent-1"


def test_get_memory_returns_clear_error_when_api_down(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: (_ for _ in ()).throw(minds.MindsError("builder api down")),
    )

    res = test_client.get("/api/v1/agent/memory")

    assert res.status_code == 502
    assert res.json()["detail"] == "builder api down"


def test_get_memory_returns_clear_error_when_key_missing(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    monkeypatch.setattr(
        minds,
        "fetch_memory",
        lambda agent_id: (_ for _ in ()).throw(
            minds.MindsConfigError("MINDS_BUILDER_API_KEY is not configured")
        ),
    )

    res = test_client.get("/api/v1/agent/memory")

    assert res.status_code == 503
    assert "MINDS_BUILDER_API_KEY" in res.json()["detail"]


def test_get_memory_returns_503_when_agent_id_not_configured(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.delenv("MINDS_AGENT_ID", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    test_client, _ = client

    res = test_client.get("/api/v1/agent/memory")

    assert res.status_code == 503
    assert "MINDS_AGENT_ID" in res.json()["detail"]


def test_update_memory_returns_503_when_agent_id_not_configured(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.delenv("MINDS_AGENT_ID", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    test_client, _ = client

    res = test_client.post(
        "/api/v1/agent/memory/update",
        json={"key": "k", "value": "v"},
    )

    assert res.status_code == 503
    assert "MINDS_AGENT_ID" in res.json()["detail"]


def test_update_memory_posts_key_value_and_returns_success(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: captured.update(agent_id=agent_id, key=key, value=value)
        or True,
    )

    res = test_client.post(
        "/api/v1/agent/memory/update",
        json={"key": "learned_insight", "value": {"ctr": 0.03}},
    )

    assert res.status_code == 200
    assert res.json() == {"success": True}
    assert captured == {
        "agent_id": "agent-1",
        "key": "learned_insight",
        "value": {"ctr": 0.03},
    }


def test_update_memory_reports_success_false_when_mind_rejects(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    monkeypatch.setattr(minds, "update_memory", lambda agent_id, key, value: False)

    res = test_client.post(
        "/api/v1/agent/memory/update",
        json={"key": "brand_voice", "value": "warm"},
    )

    assert res.status_code == 200
    assert res.json() == {"success": False}


def test_update_memory_returns_clear_error_when_api_down(
    client: tuple[TestClient, Path],
    _minds_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    monkeypatch.setattr(
        minds,
        "update_memory",
        lambda agent_id, key, value: (_ for _ in ()).throw(
            minds.MindsError("request failed: timeout")
        ),
    )

    res = test_client.post(
        "/api/v1/agent/memory/update",
        json={"key": "k", "value": "v"},
    )

    assert res.status_code == 502
    assert res.json()["detail"] == "request failed: timeout"


def test_update_memory_rejects_missing_key(
    client: tuple[TestClient, Path],
    _minds_env: None,
) -> None:
    test_client, _ = client

    res = test_client.post("/api/v1/agent/memory/update", json={"value": "v"})

    assert res.status_code == 422
