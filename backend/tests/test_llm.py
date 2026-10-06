from typing import Any

import httpx
import pytest

from app.services import llm


@pytest.fixture(autouse=True)
def _fresh_settings() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _configure_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()


def _completion(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _capture_completion(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []

    def fake_post(url, headers, json, timeout):
        requests.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(200, json=_completion('{"virality_score": 1}'))

    monkeypatch.setattr(httpx, "post", fake_post)
    return requests


# --- configuration ---


def test_unconfigured_without_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert llm.is_configured() is False
    assert llm.check_connection() == "unconfigured"


def test_openai_endpoint_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert llm.is_configured() is False
    with pytest.raises(llm.LLMConfigError, match="OPENAI_API_KEY"):
        llm._headers()


def test_local_endpoint_needs_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_llm(monkeypatch)
    assert llm.is_configured() is True
    assert llm.check_connection() == "ok"
    assert llm._headers() == {"Content-Type": "application/json"}


# --- HTTP seam ---


def test_chat_completion_posts_to_configured_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setenv("OPENAI_MODEL", "llama3.1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    requests = _capture_completion(monkeypatch)

    llm._chat_completion([{"role": "user", "content": "hi"}])

    assert requests[0]["url"] == "http://localhost:11434/v1/chat/completions"
    assert requests[0]["json"]["model"] == "llama3.1"
    assert requests[0]["json"]["messages"] == [{"role": "user", "content": "hi"}]


def test_chat_completion_sends_bearer_token_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    requests = _capture_completion(monkeypatch)

    llm._chat_completion([{"role": "user", "content": "hi"}])

    assert requests[0]["headers"]["Authorization"] == "Bearer sk-test"


def test_chat_completion_wraps_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_llm(monkeypatch)

    def fake_post(url, headers, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(llm.LLMError, match="connection refused"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_fails_closed_on_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, headers, json, timeout: httpx.Response(
            401, json={"error": "invalid api key"}
        ),
    )

    with pytest.raises(llm.LLMError, match="401"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_rejects_empty_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, headers, json, timeout: httpx.Response(
            200, json=_completion("   ")
        ),
    )

    with pytest.raises(llm.LLMError, match="empty reply"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_rejects_unexpected_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        httpx, "post", lambda url, headers, json, timeout: httpx.Response(200, json={})
    )

    with pytest.raises(llm.LLMError, match="unexpected response shape"):
        llm._chat_completion([{"role": "user", "content": "hi"}])

# --- scoring ---


def test_generate_clip_metadata_parses_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            captured.update(prompt=messages[0]["content"])
            or '{"virality_score": 82, "suggested_titles": ["A", "B"], '
            '"platform_hooks": {"youtube_shorts": ["s1"], "tiktok": ["t1"], "x": ["x1"]}}'
        ),
    )

    metadata = llm.generate_clip_metadata("hello world.", duration_seconds=21.5)

    assert metadata.virality_score == 82
    assert metadata.suggested_titles == ["A", "B"]
    assert metadata.platform_hooks["tiktok"] == ["t1"]
    assert "hello world." in captured["prompt"]
    assert "21.5s" in captured["prompt"]


def test_generate_clip_metadata_includes_chat_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            captured.update(prompt=messages[0]["content"])
            or '{"virality_score": 50, "suggested_titles": ["A"], '
            '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}'
        ),
    )

    llm.generate_clip_metadata(
        "text", chat_context='brand_voice: "bold"\nhistorical_insights: []'
    )

    assert "brand_voice" in captured["prompt"]
    assert "historical_insights" in captured["prompt"]


def test_generate_clip_metadata_strips_markdown_fences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            '```json\n{"virality_score": 10, "suggested_titles": ["A"], '
            '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}\n```'
        ),
    )

    assert llm.generate_clip_metadata("text").virality_score == 10


def test_generate_clip_metadata_clamps_score_to_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            '{"virality_score": 150, "suggested_titles": ["A"], "platform_hooks": {}}'
        ),
    )

    assert llm.generate_clip_metadata("text").virality_score == 100


def test_generate_clip_metadata_raises_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        llm, "_chat_completion", lambda messages, **kwargs: "not json at all"
    )
    with pytest.raises(llm.LLMError, match="no JSON object"):
        llm.generate_clip_metadata("text")


def test_generate_clip_metadata_refusal_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    refusal = (
        "<p>I'm not going to keep replying to the same template without hearing "
        "back from you, so let me say this once and plainly.</p>"
        "<p>This is the fourth templated prompt you've sent me - and the third "
        "copy…</p>"
    )
    monkeypatch.setattr(llm, "_chat_completion", lambda messages, **kwargs: refusal)

    with pytest.raises(llm.LLMError) as excinfo:
        llm.generate_clip_metadata("text")

    message = str(excinfo.value)
    assert "substring not found" not in message
    assert "no JSON object" in message or "refus" in message.lower()


def test_generate_clip_metadata_uses_two_step_flow_when_read_is_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prose honest read is followed by a schema-fill message; the fill's
    JSON is parsed into the verdict."""
    _configure_llm(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            calls.append(messages[-1]["content"])
            or (
                "<p>Honest read: it's a two-decade-old meme, maybe 8/100.</p>"
                if len(calls) == 1
                else '{"virality_score": 8, "suggested_titles": ["A"], '
                '"platform_hooks": {"youtube_shorts": ["s1"], "tiktok": ["t1"], "x": ["x1"]}}'
            )
        ),
    )

    metadata = llm.generate_clip_metadata("hello world.")

    assert metadata.virality_score == 8
    assert len(calls) == 2
    assert "honest read" in calls[0].lower()
    assert '"virality_score"' in calls[1]
    assert "schema" in calls[1].lower()


def test_generate_clip_metadata_skips_fill_when_read_is_parseable_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            calls.append(messages[-1]["content"])
            or '{"virality_score": 42, "suggested_titles": ["A"], '
            '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}'
        ),
    )

    metadata = llm.generate_clip_metadata("text")

    assert metadata.virality_score == 42
    assert len(calls) == 1


def test_generate_clip_metadata_raises_on_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        llm, "_chat_completion", lambda messages, **kwargs: '{"virality_score": 50}'
    )
    with pytest.raises(llm.LLMError, match="failed validation"):
        llm.generate_clip_metadata("text")


def test_generate_clip_metadata_raises_on_empty_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, headers, json, timeout: httpx.Response(
            200, json=_completion("   ")
        ),
    )
    with pytest.raises(llm.LLMError, match="empty reply"):
        llm.generate_clip_metadata("text")


VARIANTS = [
    {"variant_id": "v1", "title": "Hook A", "views": 600, "clicks": 30, "ctr": 5.0},
    {"variant_id": "v2", "title": "Hook B", "views": 400, "clicks": 8, "ctr": 2.0},
]


CLIP = {
    "id": "clip-1",
    "title": "My clip",
    "start_time": 2.0,
    "end_time": 32.0,
    "transcript": "hello world.",
}
SEGMENTS = [
    {"text": "hello", "start": 0.0, "end": 2.0},
    {"text": "world.", "start": 2.0, "end": 4.0},
]


def _youtube_long_form_reply() -> str:
    return (
        '{"chapters": [{"title": "Hook", "timestamp": 2.0}], '
        '"tags": ["editing", "storytime"], '
        '"poll": {"question": "Which?", "options": ["A", "B"]}, '
        '"quiz": [{"question": "What?", "answer": "This"}], '
        '"thumbnail_briefs": ['
        '{"frame_timestamp": 3.0, "overlay_text": "one"}, '
        '{"frame_timestamp": 4.0, "overlay_text": "two"}, '
        '{"frame_timestamp": 5.0, "overlay_text": "three"}], '
        '"shorts_link": "Why I left YouTube"}'
    )


# --- adaptations ---


def test_generate_adaptation_features_parses_long_form_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            captured.update(prompt=messages[0]["content"]) or _youtube_long_form_reply()
        ),
    )

    manifest = llm.generate_adaptation_features(
        CLIP, "youtube", "LONG_FORM", SEGMENTS, chat_context='brand_voice: "bold"'
    )

    assert manifest.platform == "youtube"
    assert manifest.surface == "LONG_FORM"
    assert manifest.chapters[0].title == "Hook"
    assert manifest.tags == ["editing", "storytime"]
    assert manifest.poll.question == "Which?"
    assert manifest.poll.options == ["A", "B"]
    assert manifest.quiz[0].answer == "This"
    assert len(manifest.thumbnail_briefs) == 3
    assert manifest.thumbnail_briefs[0].overlay_text == "one"
    assert "youtube (LONG_FORM)" in captured["prompt"]
    assert "hello world." in captured["prompt"]
    assert "brand_voice" in captured["prompt"]
    assert "[2.0s → 4.0s] world." in captured["prompt"]


def test_generate_adaptation_features_accepts_surface_echo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    echoed = _youtube_long_form_reply().replace(
        '{"chapters"', '{"surface": "LONG_FORM", "chapters"', 1
    )
    monkeypatch.setattr(llm, "_chat_completion", lambda messages, **kwargs: echoed)
    manifest = llm.generate_adaptation_features(
        CLIP, "youtube", "LONG_FORM", SEGMENTS
    )
    assert manifest.surface == "LONG_FORM"


def test_generate_adaptation_features_rejects_surface_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    echoed = _youtube_long_form_reply().replace(
        '{"chapters"', '{"surface": "SHORTS", "chapters"', 1
    )
    monkeypatch.setattr(llm, "_chat_completion", lambda messages, **kwargs: echoed)
    with pytest.raises(llm.LLMError, match="expected 'LONG_FORM'"):
        llm.generate_adaptation_features(CLIP, "youtube", "LONG_FORM", SEGMENTS)


def test_generate_adaptation_features_enforces_three_thumbnail_briefs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    reply = (
        '{"thumbnail_briefs": ['
        '{"frame_timestamp": 3.0, "overlay_text": "one"}, '
        '{"frame_timestamp": 4.0, "overlay_text": "two"}], '
        '"platform_hooks": ["hook"]}'
    )
    monkeypatch.setattr(llm, "_chat_completion", lambda messages, **kwargs: reply)
    with pytest.raises(llm.LLMError, match="exactly 3 thumbnail_briefs"):
        llm.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)


def test_generate_adaptation_features_validates_tiktok_post_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            '{"overlay_spec": [{"text": "t", "placement": "center", "style": "bold"}]}'
        ),
    )
    with pytest.raises(llm.LLMError, match="requires caption_style"):
        llm.generate_adaptation_features(CLIP, "tiktok", "POST", SEGMENTS)


def test_generate_adaptation_features_requires_x_caption_and_hashtags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(
        llm, "_chat_completion", lambda messages, **kwargs: '{"caption": "hot take"}'
    )
    with pytest.raises(llm.LLMError, match="requires hashtags"):
        llm.generate_adaptation_features(CLIP, "x", "POST", SEGMENTS)


def test_generate_adaptation_features_uses_two_step_flow_when_read_is_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prose read (the Mind refusing the single-shot JSON shape) is followed
    by a schema-fill message; the fill's JSON is parsed into the manifest."""
    _configure_llm(monkeypatch)
    calls: list[str] = []
    refusal = (
        "<p>Hey - seventeenth round, new prompt shape. Same lane issues with "
        "three new wrinkles, and the clip is real so I'll engage the parts I "
        "can engage honestly.</p>"
        "<p>Three flags on the prompt before any { real engagement } happens... "
        "the shape demands a fabricated manifest.</p>"
    )
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda messages, **kwargs: (
            calls.append(messages[-1]["content"])
            or (refusal if len(calls) == 1 else _youtube_long_form_reply())
        ),
    )

    manifest = llm.generate_adaptation_features(
        CLIP, "youtube", "LONG_FORM", SEGMENTS, chat_context='brand_voice: "bold"'
    )

    assert manifest.chapters[0].title == "Hook"
    assert len(calls) == 2
    assert "honest read" in calls[0].lower()
    assert '"chapters"' in calls[1]


def test_generate_adaptation_features_prose_reply_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prose reply that merely contains braces must not leak a raw
    json.JSONDecodeError like 'Expecting value: line 1 column 13'."""
    _configure_llm(monkeypatch)
    refusal = (
        "<p>the clip is real so I'll engage the parts I can engage honestly "
        "{ not a manifest }</p>"
    )
    monkeypatch.setattr(llm, "_chat_completion", lambda messages, **kwargs: refusal)

    with pytest.raises(llm.LLMError) as excinfo:
        llm.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)

    message = str(excinfo.value)
    assert "Expecting value" not in message
    assert "no JSON object" in message or "refus" in message.lower()


def test_generate_adaptation_features_raises_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(llm, "_chat_completion", lambda messages, **kwargs: "not json")
    with pytest.raises(llm.LLMError, match="no JSON object"):
        llm.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)


def test_generate_adaptation_features_raises_on_empty_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_llm(monkeypatch)
    monkeypatch.setattr(llm, "_chat_completion", lambda messages, **kwargs: "")
    with pytest.raises(llm.LLMError, match="no JSON object|empty reply"):
        llm.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)
