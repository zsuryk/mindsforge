from typing import Any

import httpx
import pytest
from app.services import minds


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        return self._payload


def _configure_minds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_settings() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_fetch_memory_returns_context_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_minds(monkeypatch)
    calls: list[tuple[Any, ...]] = []

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        return FakeResponse({"brand_voice": "bold", "historical_insights": []})

    monkeypatch.setattr(minds.httpx, "get", fake_get)

    memory = minds.fetch_memory("agent-1")

    assert memory == {"brand_voice": "bold", "historical_insights": []}
    url, headers, _ = calls[0]
    assert url == f"{minds.MINDS_BUILDER_BASE_URL}/minds/agent-1/memory"
    assert headers == {minds.BUILDER_API_KEY_HEADER: "test-builder-key"}


def test_fetch_memory_raises_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx, "get", lambda url, headers, timeout: FakeResponse({}, status_code=500)
    )
    with pytest.raises(minds.MindsError, match="status 500"):
        minds.fetch_memory("agent-1")


def test_fetch_memory_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDS_BUILDER_API_KEY", raising=False)
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(minds.MindsConfigError, match="MINDS_BUILDER_API_KEY"):
        minds.fetch_memory("agent-1")


def test_fetch_memory_requires_agent_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.delenv("MINDS_AGENT_ID", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(minds.MindsConfigError, match="MINDS_AGENT_ID"):
        minds._agent_id()


def test_fetch_memory_raises_on_non_json_body(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_minds(monkeypatch)

    class NonJsonResponse:
        status_code = 200

        def json(self) -> Any:
            raise ValueError("expected a JSON body")

    monkeypatch.setattr(minds.httpx, "get", lambda url, headers, timeout: NonJsonResponse())
    with pytest.raises(minds.MindsError, match="non-JSON"):
        minds.fetch_memory("agent-1")


def test_fetch_memory_raises_on_non_object_body(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx, "get", lambda url, headers, timeout: FakeResponse([], status_code=200)
    )
    with pytest.raises(minds.MindsError, match="unexpected shape"):
        minds.fetch_memory("agent-1")


def test_network_errors_are_wrapped_as_minds_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "get",
        lambda url, headers, timeout: (_ for _ in ()).throw(
            httpx.TimeoutException("timed out")
        ),
    )
    with pytest.raises(minds.MindsError, match="timed out"):
        minds.fetch_memory("agent-1")


def test_update_memory_posts_key_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_minds(monkeypatch)
    calls: list[tuple[Any, ...]] = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json))
        return FakeResponse({"success": True})

    monkeypatch.setattr(minds.httpx, "post", fake_post)

    result = minds.update_memory("agent-1", "learned_insight", {"ctr": 0.03})

    assert result is True
    url, headers, body = calls[0]
    assert url == f"{minds.MINDS_BUILDER_BASE_URL}/minds/agent-1/memory/update"
    assert headers == {minds.BUILDER_API_KEY_HEADER: "test-builder-key"}
    assert body == {"key": "learned_insight", "value": {"ctr": 0.03}}


def test_update_memory_returns_false_when_success_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx, "post", lambda url, headers, json, timeout: FakeResponse({})
    )
    assert minds.update_memory("agent-1", "k", "v") is False


def test_update_memory_returns_false_on_non_object_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx, "post", lambda url, headers, json, timeout: FakeResponse("true")
    )
    assert minds.update_memory("agent-1", "k", "v") is False


def test_generate_clip_metadata_parses_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_minds(monkeypatch)
    calls: list[tuple[Any, ...]] = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, json))
        return FakeResponse(
            {
                "response": (
                    '{"virality_score": 82, "suggested_titles": ["A", "B"], '
                    '"platform_hooks": {"youtube_shorts": ["s1"], "tiktok": ["t1"], "x": ["x1"]}}'
                )
            }
        )

    monkeypatch.setattr(minds.httpx, "post", fake_post)

    metadata = minds.generate_clip_metadata("hello world.", duration_seconds=21.5)

    assert metadata.virality_score == 82
    assert metadata.suggested_titles == ["A", "B"]
    assert metadata.platform_hooks["tiktok"] == ["t1"]
    url, body = calls[0]
    assert url == f"{minds.MINDS_BUILDER_BASE_URL}/minds/agent-1/message"
    assert "hello world." in body["prompt"]
    assert "21.5s" in body["prompt"]


def test_generate_clip_metadata_includes_memory_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_post(url, headers, json, timeout):
        captured["prompt"] = json["prompt"]
        return FakeResponse(
            {
                "response": (
                    '{"virality_score": 50, "suggested_titles": ["A"], '
                    '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}'
                )
            }
        )

    monkeypatch.setattr(minds.httpx, "post", fake_post)

    minds.generate_clip_metadata(
        "text",
        memory_context="brand_voice: \"bold\"\nhistorical_insights: []",
    )

    assert "brand_voice" in captured["prompt"]
    assert "historical_insights" in captured["prompt"]


def test_generate_clip_metadata_strips_markdown_fences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: FakeResponse(
            {
                "response": (
                    '```json\n{"virality_score": 10, "suggested_titles": ["A"], '
                    '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}\n```'
                )
            }
        ),
    )

    metadata = minds.generate_clip_metadata("text")

    assert metadata.virality_score == 10


def test_generate_clip_metadata_clamps_score_to_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: FakeResponse(
            {
                "response": (
                    '{"virality_score": 150, "suggested_titles": ["A"], '
                    '"platform_hooks": {}}'
                )
            }
        ),
    )

    assert minds.generate_clip_metadata("text").virality_score == 100


def test_generate_clip_metadata_raises_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: FakeResponse({"response": "not json at all"}),
    )
    with pytest.raises(minds.MindsError, match="Could not parse"):
        minds.generate_clip_metadata("text")


def test_generate_clip_metadata_raises_on_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: FakeResponse(
            {"response": '{"virality_score": 50}'}
        ),
    )
    with pytest.raises(minds.MindsError, match="failed validation"):
        minds.generate_clip_metadata("text")


def test_generate_clip_metadata_raises_on_missing_response_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx, "post", lambda url, headers, json, timeout: FakeResponse({})
    )
    with pytest.raises(minds.MindsError, match="missing 'response'"):
        minds.generate_clip_metadata("text")


def test_generate_clip_metadata_requires_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MINDS_BUILDER_API_KEY", raising=False)
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(minds.MindsError, match="MINDS_BUILDER_API_KEY"):
        minds.generate_clip_metadata("text")


def test_build_memory_context_renders_known_keys() -> None:
    context = minds.build_memory_context(
        {
            "creator_id": "creator-7",
            "brand_voice": "bold",
            "historical_insights": {"tiktok": ["fast pacing"]},
            "ab_test_history": [{"winning_variant_id": "v1"}],
        }
    )
    assert "creator_id: \"creator-7\"" in context
    assert "brand_voice: \"bold\"" in context
    assert "historical_insights" in context
    assert "ab_test_history" in context


VARIANTS = [
    {"variant_id": "v1", "title": "Hook A", "views": 600, "clicks": 30, "ctr": 5.0},
    {"variant_id": "v2", "title": "Hook B", "views": 400, "clicks": 8, "ctr": 2.0},
]


def test_decide_experiment_winner_parses_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_minds(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_post(url, headers, json, timeout):
        captured["prompt"] = json["prompt"]
        return FakeResponse(
            {
                "response": (
                    '{"winning_variant_id": "v1", '
                    '"reasoning": "Hook A held viewers longer; reuse this formula."}'
                )
            }
        )

    monkeypatch.setattr(minds.httpx, "post", fake_post)

    verdict = minds.decide_experiment_winner(
        "youtube_shorts",
        VARIANTS,
        "the clip transcript",
        memory_context="brand_voice: \"bold\"",
    )

    assert verdict.winning_variant_id == "v1"
    assert "reuse this formula" in verdict.reasoning
    assert "youtube_shorts" in captured["prompt"]
    assert "the clip transcript" in captured["prompt"]
    assert "v2" in captured["prompt"]
    assert "brand_voice" in captured["prompt"]


def test_decide_experiment_winner_strips_markdown_fences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: FakeResponse(
            {
                "response": (
                    '```json\n{"winning_variant_id": "v2", '
                    '"reasoning": "debate-style hook won."}\n```'
                )
            }
        ),
    )
    verdict = minds.decide_experiment_winner("x", VARIANTS, "t")
    assert verdict.winning_variant_id == "v2"


def test_decide_experiment_winner_rejects_unknown_winner_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: FakeResponse(
            {
                "response": (
                    '{"winning_variant_id": "ghost", "reasoning": "it felt right"}'
                )
            }
        ),
    )
    with pytest.raises(minds.MindsError, match="unknown variant id"):
        minds.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_rejects_empty_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: FakeResponse(
            {"response": '{"winning_variant_id": "v1", "reasoning": "   "}'}
        ),
    )
    with pytest.raises(minds.MindsError, match="failed validation"):
        minds.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_raises_on_missing_response_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx, "post", lambda url, headers, json, timeout: FakeResponse({})
    )
    with pytest.raises(minds.MindsError, match="missing 'response'"):
        minds.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_raises_on_non_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: FakeResponse({}, status_code=500),
    )
    with pytest.raises(minds.MindsError, match="status 500"):
        minds.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_requires_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MINDS_BUILDER_API_KEY", raising=False)
    monkeypatch.setenv("MINDS_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(minds.MindsError, match="MINDS_BUILDER_API_KEY"):
        minds.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_build_memory_context_falls_back_to_whole_tree() -> None:
    context = minds.build_memory_context({"unexpected_key": {"nested": True}})
    assert "unexpected_key" in context
    assert context == '{"unexpected_key": {"nested": true}}'
