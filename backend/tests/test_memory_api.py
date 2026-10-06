from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import llm


def test_get_memory_returns_local_agent_id_and_tree(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    memory = {"brand_voice": "bold", "historical_insights": {"tiktok": ["fast pacing"]}}
    monkeypatch.setattr(llm, "fetch_memory", lambda: memory)

    res = test_client.get("/api/v1/agent/memory")

    assert res.status_code == 200
    assert res.json() == {"agent_id": llm.LOCAL_AGENT_ID, "memory": memory}


def test_get_memory_returns_clear_error_when_store_fails(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    monkeypatch.setattr(
        llm,
        "fetch_memory",
        lambda: (_ for _ in ()).throw(llm.LLMError("memory store down")),
    )

    res = test_client.get("/api/v1/agent/memory")

    assert res.status_code == 502
    assert res.json()["detail"] == "memory store down"


def test_get_memory_returns_clear_error_when_unconfigured(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    monkeypatch.setattr(
        llm,
        "fetch_memory",
        lambda: (_ for _ in ()).throw(
            llm.LLMConfigError("OPENAI_BASE_URL is not configured")
        ),
    )

    res = test_client.get("/api/v1/agent/memory")

    assert res.status_code == 503
    assert "OPENAI_BASE_URL" in res.json()["detail"]


def test_update_memory_persists_key_value_and_returns_success(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        llm,
        "update_memory",
        lambda key, value: captured.update(key=key, value=value) or True,
    )

    res = test_client.post(
        "/api/v1/agent/memory/update",
        json={"key": "learned_insight", "value": {"ctr": 0.03}},
    )

    assert res.status_code == 200
    assert res.json() == {"success": True}
    assert captured == {"key": "learned_insight", "value": {"ctr": 0.03}}


def test_update_memory_reports_success_false_when_store_rejects(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    monkeypatch.setattr(llm, "update_memory", lambda key, value: False)

    res = test_client.post(
        "/api/v1/agent/memory/update",
        json={"key": "brand_voice", "value": "warm"},
    )

    assert res.status_code == 200
    assert res.json() == {"success": False}


def test_update_memory_returns_clear_error_when_store_fails(
    client: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = client
    monkeypatch.setattr(
        llm,
        "update_memory",
        lambda key, value: (_ for _ in ()).throw(llm.LLMError("memory store down")),
    )

    res = test_client.post(
        "/api/v1/agent/memory/update",
        json={"key": "k", "value": "v"},
    )

    assert res.status_code == 502
    assert res.json()["detail"] == "memory store down"


def test_update_memory_rejects_missing_key(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client

    res = test_client.post("/api/v1/agent/memory/update", json={"value": "v"})

    assert res.status_code == 422


def test_memory_round_trips_through_the_local_store(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client

    test_client.post(
        "/api/v1/agent/memory/update",
        json={"key": "brand_voice", "value": "bold"},
    )

    memory = test_client.get("/api/v1/agent/memory").json()["memory"]
    assert memory == {"brand_voice": "bold"}
