import json
from typing import Any

import httpx
import pytest

from app.services import llm

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

METADATA_VERDICT = (
    '{"virality_score": 82, "suggested_titles": ["A", "B"], '
    '"platform_hooks": {"youtube_shorts": ["s1"], "tiktok": ["t1"], "x": ["x1"]}}'
)

EXPERIMENT_VERDICT = (
    '{"winning_variant_id": "v1", "reasoning": "Hook A held viewers longer; '
    'reuse this formula."}'
)


def youtube_long_form_reply() -> str:
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


# --- configuration ---


def test_unconfigured_without_base_url(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm(base_url="")

    assert llm.is_configured() is False
    assert llm.check_connection() == "unconfigured"
    # Fail-closed: the probe never reaches the network.
    assert llm_http.requests == []


def test_openai_endpoint_requires_api_key(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm("https://api.openai.com/v1", "")

    assert llm.is_configured() is False
    with pytest.raises(llm.LLMConfigError, match="OPENAI_API_KEY"):
        llm._headers()

    # Every prompt fails closed before any request is attempted.
    with pytest.raises(llm.LLMConfigError, match="OPENAI_API_KEY"):
        llm.generate_clip_metadata("hello world.")
    with pytest.raises(llm.LLMConfigError, match="OPENAI_API_KEY"):
        llm.decide_experiment_winner("youtube_shorts", VARIANTS, "t")
    with pytest.raises(llm.LLMConfigError, match="OPENAI_API_KEY"):
        llm.generate_adaptation_features(CLIP, "youtube", "LONG_FORM", SEGMENTS)
    assert llm_http.requests == []


def test_missing_base_url_fails_every_prompt_closed(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm(base_url="")

    with pytest.raises(llm.LLMConfigError, match="OPENAI_BASE_URL"):
        llm.generate_clip_metadata("hello world.")
    with pytest.raises(llm.LLMConfigError, match="OPENAI_BASE_URL"):
        llm.decide_experiment_winner("youtube_shorts", VARIANTS, "t")
    with pytest.raises(llm.LLMConfigError, match="OPENAI_BASE_URL"):
        llm.generate_adaptation_features(CLIP, "youtube", "LONG_FORM", SEGMENTS)
    assert llm_http.requests == []


def test_local_endpoint_needs_no_api_key(configure_llm: Any) -> None:
    configure_llm()

    assert llm.is_configured() is True
    assert llm._headers() == {"Content-Type": "application/json"}


def test_configured_sends_bearer_token(configure_llm: Any, llm_http: Any) -> None:
    configure_llm("https://api.openai.com/v1", "sk-test")
    llm_http.reply_with(METADATA_VERDICT)

    llm.generate_clip_metadata("text")

    assert llm_http.completion_requests[0].headers["Authorization"] == "Bearer sk-test"


def test_base_url_trailing_slash_does_not_double_up(configure_llm: Any, llm_http: Any) -> None:
    configure_llm("http://localhost:11434/v1/")
    llm_http.reply_with(METADATA_VERDICT)

    llm.generate_clip_metadata("text")

    assert llm_http.urls == ["http://localhost:11434/v1/chat/completions"]


def test_configured_model_is_used(configure_llm: Any, llm_http: Any) -> None:
    configure_llm(model="llama3.1")
    llm_http.reply_with(METADATA_VERDICT)

    llm.generate_clip_metadata("text")

    assert json.loads(llm_http.completion_requests[0].content)["model"] == "llama3.1"


# --- health probe ---


def test_check_connection_probes_models_endpoint(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()

    assert llm.check_connection() == "ok"
    assert llm_http.urls == ["http://localhost:11434/v1/models"]


def test_check_connection_down_on_non_200(configure_llm: Any, llm_http: Any) -> None:
    configure_llm()
    llm_http.models_status_is(503)

    assert llm.check_connection() == "down"


def test_check_connection_down_on_request_error(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.fail_with(httpx.ConnectError("connection refused"))

    assert llm.check_connection() == "down"


# --- HTTP seam and error mapping ---


def test_chat_completion_posts_messages_array(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("reply text")

    assert llm._chat_completion([{"role": "user", "content": "hi"}]) == "reply text"
    assert llm_http.roles(0) == ["user"]
    assert llm_http.prompt(0) == "hi"


def test_chat_completion_wraps_transport_errors(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.fail_with(httpx.ConnectError("connection refused"))

    with pytest.raises(llm.LLMError, match="connection refused"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_wraps_timeouts(configure_llm: Any, llm_http: Any) -> None:
    configure_llm()
    llm_http.fail_with(httpx.ReadTimeout("timed out"))

    with pytest.raises(llm.LLMError, match="timed out"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_maps_error_status_to_llm_error(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.completions_status_is(401).reply_with("invalid api key")

    with pytest.raises(llm.LLMError) as excinfo:
        llm._chat_completion([{"role": "user", "content": "hi"}])

    assert "401" in str(excinfo.value)


def test_chat_completion_rejects_empty_reply(configure_llm: Any, llm_http: Any) -> None:
    configure_llm()
    llm_http.reply_with("   ")

    with pytest.raises(llm.LLMError, match="empty reply"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_rejects_unexpected_shape(
    configure_llm: Any, llm_http: Any
) -> None:
    """An OpenAI-shaped response missing ``choices`` fails closed rather than
    raising a raw KeyError out of the client."""
    configure_llm()
    llm_http.respond_with(lambda request: httpx.Response(200, json={"error": "nope"}))

    with pytest.raises(llm.LLMError, match="unexpected response shape"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_rejects_non_json_body(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.respond_with(
        lambda request: httpx.Response(200, text="<html>proxy error</html>")
    )

    with pytest.raises(llm.LLMError, match="unexpected response shape"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_rejects_non_string_content(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.respond_with(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": None}}]},
        )
    )

    with pytest.raises(llm.LLMError, match="empty reply"):
        llm._chat_completion([{"role": "user", "content": "hi"}])


# --- clip scoring ---


def test_generate_clip_metadata_parses_verdict(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(METADATA_VERDICT)

    metadata = llm.generate_clip_metadata("hello world.", duration_seconds=21.5)

    assert metadata.virality_score == 82
    assert metadata.suggested_titles == ["A", "B"]
    assert metadata.platform_hooks["tiktok"] == ["t1"]
    prompt = llm_http.prompt(0)
    assert "hello world." in prompt
    assert "21.5s" in prompt


def test_generate_clip_metadata_includes_chat_context(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(METADATA_VERDICT)

    llm.generate_clip_metadata(
        "text", chat_context='brand_voice: "bold"\nhistorical_insights: []'
    )

    assert "brand_voice" in llm_http.prompt(0)
    assert "historical_insights" in llm_http.prompt(0)


def test_generate_clip_metadata_states_when_no_context(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(METADATA_VERDICT)

    llm.generate_clip_metadata("text")

    assert "no creator conversation context" in llm_http.prompt(0)


def test_generate_clip_metadata_strips_markdown_fences(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        '```json\n{"virality_score": 10, "suggested_titles": ["A"], '
        '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}\n```'
    )

    assert llm.generate_clip_metadata("text").virality_score == 10


def test_generate_clip_metadata_clamps_score_to_range(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        '{"virality_score": 150, "suggested_titles": ["A"], "platform_hooks": {}}'
    )

    assert llm.generate_clip_metadata("text").virality_score == 100


def test_generate_clip_metadata_raises_on_invalid_json(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("not json at all")

    with pytest.raises(llm.LLMError, match="no JSON object"):
        llm.generate_clip_metadata("text")


def test_generate_clip_metadata_refusal_error_is_actionable(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        "<p>I'm not going to keep replying to the same template without hearing "
        "back from you, so let me say this once and plainly.</p>"
        "<p>This is the fourth templated prompt you've sent me.</p>"
    )

    with pytest.raises(llm.LLMError) as excinfo:
        llm.generate_clip_metadata("text")

    message = str(excinfo.value)
    assert "substring not found" not in message
    assert "no JSON object" in message or "refus" in message.lower()


def test_generate_clip_metadata_uses_two_step_flow_when_read_is_prose(
    configure_llm: Any, llm_http: Any
) -> None:
    """A prose honest read is followed by a schema-fill message; the fill's
    JSON is parsed into the verdict."""
    configure_llm()
    llm_http.reply_with(
        "<p>Honest read: it's a two-decade-old meme, maybe 8/100.</p>",
        METADATA_VERDICT.replace('"virality_score": 82', '"virality_score": 8'),
    )

    metadata = llm.generate_clip_metadata("hello world.")

    assert metadata.virality_score == 8
    assert len(llm_http.completion_requests) == 2
    assert "honest read" in llm_http.prompt(0).lower()
    assert '"virality_score"' in llm_http.prompt(1)
    assert "schema" in llm_http.prompt(1).lower()
    # The fill replays the read as the assistant turn.
    assert llm_http.roles(1) == ["user", "assistant", "user"]


def test_generate_clip_metadata_skips_fill_when_read_is_parseable_json(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(METADATA_VERDICT)

    metadata = llm.generate_clip_metadata("text")

    assert metadata.virality_score == 82
    assert len(llm_http.completion_requests) == 1


def test_generate_clip_metadata_raises_on_missing_fields(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with('{"virality_score": 50}')

    with pytest.raises(llm.LLMError, match="failed validation"):
        llm.generate_clip_metadata("text")


def test_generate_clip_metadata_propagates_transport_failure(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.fail_with(httpx.ConnectError("connection refused"))

    with pytest.raises(llm.LLMError, match="connection refused"):
        llm.generate_clip_metadata("text")


# --- adaptations ---


def test_generate_adaptation_features_parses_long_form_manifest(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(youtube_long_form_reply())

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
    prompt = llm_http.prompt(0)
    assert "youtube (LONG_FORM)" in prompt
    assert "hello world." in prompt
    assert "brand_voice" in prompt
    assert "[2.0s → 4.0s] world." in prompt


def test_generate_adaptation_features_accepts_surface_echo(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        youtube_long_form_reply().replace(
            '{"chapters"', '{"surface": "LONG_FORM", "chapters"', 1
        )
    )

    manifest = llm.generate_adaptation_features(CLIP, "youtube", "LONG_FORM", SEGMENTS)

    assert manifest.surface == "LONG_FORM"


def test_generate_adaptation_features_rejects_surface_mismatch(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        youtube_long_form_reply().replace(
            '{"chapters"', '{"surface": "SHORTS", "chapters"', 1
        )
    )

    with pytest.raises(llm.LLMError, match="expected 'LONG_FORM'"):
        llm.generate_adaptation_features(CLIP, "youtube", "LONG_FORM", SEGMENTS)


def test_generate_adaptation_features_enforces_three_thumbnail_briefs(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        '{"thumbnail_briefs": ['
        '{"frame_timestamp": 3.0, "overlay_text": "one"}, '
        '{"frame_timestamp": 4.0, "overlay_text": "two"}], '
        '"platform_hooks": ["hook"]}'
    )

    with pytest.raises(llm.LLMError, match="exactly 3 thumbnail_briefs"):
        llm.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)


def test_generate_adaptation_features_validates_tiktok_post_shape(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        '{"overlay_spec": [{"text": "t", "placement": "center", "style": "bold"}]}'
    )

    with pytest.raises(llm.LLMError, match="requires caption_style"):
        llm.generate_adaptation_features(CLIP, "tiktok", "POST", SEGMENTS)


def test_generate_adaptation_features_requires_x_caption_and_hashtags(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with('{"caption": "hot take"}')

    with pytest.raises(llm.LLMError, match="requires hashtags"):
        llm.generate_adaptation_features(CLIP, "x", "POST", SEGMENTS)


def test_generate_adaptation_features_uses_two_step_flow_when_read_is_prose(
    configure_llm: Any, llm_http: Any
) -> None:
    """A prose read (the model refusing the single-shot JSON shape) is
    followed by a schema-fill message; the fill's JSON becomes the manifest."""
    configure_llm()
    llm_http.reply_with(
        "<p>Hey - seventeenth round, new prompt shape. Same lane issues with "
        "three new wrinkles, and the clip is real so I'll engage honestly.</p>",
        youtube_long_form_reply(),
    )

    manifest = llm.generate_adaptation_features(
        CLIP, "youtube", "LONG_FORM", SEGMENTS, chat_context='brand_voice: "bold"'
    )

    assert manifest.chapters[0].title == "Hook"
    assert len(llm_http.completion_requests) == 2
    assert "honest read" in llm_http.prompt(0).lower()
    assert '"chapters"' in llm_http.prompt(1)


def test_generate_adaptation_features_prose_reply_error_is_actionable(
    configure_llm: Any, llm_http: Any
) -> None:
    """A prose reply that merely contains braces must not leak a raw
    json.JSONDecodeError like 'Expecting value: line 1 column 13'."""
    configure_llm()
    llm_http.reply_with(
        "<p>the clip is real so I'll engage the parts I can engage honestly "
        "{ not a manifest }</p>"
    )

    with pytest.raises(llm.LLMError) as excinfo:
        llm.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)

    message = str(excinfo.value)
    assert "Expecting value" not in message
    assert "no JSON object" in message or "refus" in message.lower()


def test_generate_adaptation_features_raises_on_invalid_json(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("not json")

    with pytest.raises(llm.LLMError, match="no JSON object"):
        llm.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)


def test_generate_adaptation_features_raises_on_empty_reply(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("")

    with pytest.raises(llm.LLMError, match="empty reply"):
        llm.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)


def test_generate_adaptation_features_rejects_unsupported_target(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("{}")

    with pytest.raises(llm.LLMError, match="Unsupported adaptation target"):
        llm.generate_adaptation_features(CLIP, "youtube", "LIVE", SEGMENTS)


# --- experiment verdicts ---


def test_decide_experiment_winner_parses_verdict(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(EXPERIMENT_VERDICT)

    verdict = llm.decide_experiment_winner(
        "youtube_shorts",
        VARIANTS,
        "the clip transcript",
        chat_context='brand_voice: "bold"',
    )

    assert verdict.winning_variant_id == "v1"
    assert "reuse this formula" in verdict.reasoning
    prompt = llm_http.prompt(0)
    assert "youtube_shorts" in prompt
    assert "the clip transcript" in prompt
    assert "v2" in prompt
    assert "brand_voice" in prompt


def test_decide_experiment_winner_strips_markdown_fences(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        '```json\n{"winning_variant_id": "v2", '
        '"reasoning": "debate-style hook won."}\n```'
    )

    assert llm.decide_experiment_winner("x", VARIANTS, "t").winning_variant_id == "v2"


def test_decide_experiment_winner_rejects_unknown_winner_id(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        '{"winning_variant_id": "ghost", "reasoning": "it felt right"}'
    )

    with pytest.raises(llm.LLMError, match="unknown variant id"):
        llm.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_rejects_empty_reasoning(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with('{"winning_variant_id": "v1", "reasoning": "   "}')

    with pytest.raises(llm.LLMError, match="failed validation"):
        llm.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_raises_on_empty_reply(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with("  ")

    with pytest.raises(llm.LLMError, match="empty reply"):
        llm.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_two_step_flow(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(
        "Looking at the three variants, variant v1 with its hook-driven title "
        "clearly outperformed the others. The 5% CTR versus 2% shows viewers "
        "responded to the stronger opening.",
        EXPERIMENT_VERDICT,
    )

    verdict = llm.decide_experiment_winner("youtube_shorts", VARIANTS, "t")

    assert verdict.winning_variant_id == "v1"
    assert len(llm_http.completion_requests) == 2


def test_decide_experiment_winner_skips_fill_when_read_is_json(
    configure_llm: Any, llm_http: Any
) -> None:
    configure_llm()
    llm_http.reply_with(EXPERIMENT_VERDICT)

    verdict = llm.decide_experiment_winner("youtube_shorts", VARIANTS, "t")

    assert verdict.winning_variant_id == "v1"
    assert len(llm_http.completion_requests) == 1


def test_decide_experiment_winner_rejects_unknown_id_from_fill_step(
    configure_llm: Any, llm_http: Any
) -> None:
    """A read that parses as JSON but names a variant that does not exist must
    still go through the fill step before failing closed."""
    configure_llm()
    llm_http.reply_with(
        '{"winning_variant_id": "ghost", "reasoning": "it felt right"}',
        EXPERIMENT_VERDICT,
    )

    verdict = llm.decide_experiment_winner("youtube_shorts", VARIANTS, "t")

    assert verdict.winning_variant_id == "v1"
    assert len(llm_http.completion_requests) == 2


# --- local memory store ---


def test_fetch_memory_returns_empty_tree_initially(client: tuple[Any, Any]) -> None:
    assert llm.fetch_memory() == {}


def test_update_memory_persists_key_value(client: tuple[Any, Any]) -> None:
    assert llm.update_memory("brand_voice", "bold") is True
    assert llm.fetch_memory() == {"brand_voice": "bold"}


def test_update_memory_overwrites_existing_key(client: tuple[Any, Any]) -> None:
    llm.update_memory("k", 1)
    llm.update_memory("k", 2)

    assert llm.fetch_memory() == {"k": 2}


def test_update_memory_stores_structured_values(client: tuple[Any, Any]) -> None:
    llm.update_memory("ab_test_history", [{"experiment_id": "e1"}])

    assert llm.fetch_memory() == {"ab_test_history": [{"experiment_id": "e1"}]}


def test_memory_is_scoped_to_the_local_agent_id(client: tuple[Any, Any]) -> None:
    """Another agent's rows are invisible: the local id is the only key used."""
    from app.db.base import get_session_factory
    from app.models.memory import MemoryEntry

    with get_session_factory()() as db:
        db.add(MemoryEntry(agent_id="other-agent", key="brand_voice", value="theirs"))
        db.commit()

    assert llm.fetch_memory() == {}

    llm.update_memory("brand_voice", "mine")

    assert llm.fetch_memory() == {"brand_voice": "mine"}


# --- chat thread storage ---


def test_notify_mind_persists_marked_system_row(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()

    llm.notify_mind("Experiment concluded on clip 'My clip'.")

    rows = llm._chat_rows()
    assert len(rows) == 2
    assert rows[0].role == "system"
    assert rows[0].text == llm.CHAT_INIT_INSTRUCTION
    assert rows[1].role == "system"
    assert rows[1].text == f"{llm.SYSTEM_MARKER}Experiment concluded on clip 'My clip'."


def test_notify_mind_swallows_store_failure(
    client: tuple[Any, Any],
    configure_llm: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_llm()
    monkeypatch.setattr(
        llm,
        "_insert_chat_row",
        lambda role, text: (_ for _ in ()).throw(RuntimeError("disk full")),
    )
    captured: list[str] = []
    monkeypatch.setattr(
        llm.logger, "warning", lambda message, *args: captured.append(message)
    )

    assert llm.notify_mind("hello") is None
    assert any("notification not delivered" in message for message in captured)


def test_post_chat_notification_is_visible_in_history(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()

    llm.post_chat_notification("Trend results for 'ai video'")

    messages = llm.fetch_chat_history()
    assert messages[-1].role == "system"
    # The marker is stripped for the UI.
    assert messages[-1].text == "Trend results for 'ai video'"


# --- build_chat_context ---


def test_build_chat_context_returns_none_on_empty_history(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()

    assert llm.build_chat_context() is None


def test_build_chat_context_returns_none_when_only_the_instruction_exists(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()
    llm._insert_chat_row("system", llm.CHAT_INIT_INSTRUCTION)

    assert llm.build_chat_context() is None


def test_build_chat_context_renders_role_annotations(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()
    llm._insert_chat_row("user", "Hello Mind!")
    llm._insert_chat_row("mind", "Hi creator!")
    llm._insert_chat_row("system", f"{llm.SYSTEM_MARKER}Trend results here")

    context = llm.build_chat_context()

    assert context is not None
    assert "Creator: Hello Mind!" in context
    assert "Mind: Hi creator!" in context
    assert "[System]: Trend results here" in context
    # Oldest first, so the model reads the thread in order.
    assert context.index("Creator:") < context.index("Mind:") < context.index("[System]:")


def test_build_chat_context_excludes_init_instruction(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()
    llm._insert_chat_row("system", llm.CHAT_INIT_INSTRUCTION)
    llm._insert_chat_row("user", "Actual message")

    context = llm.build_chat_context()

    assert context is not None
    assert llm.CHAT_INIT_INSTRUCTION not in context
    assert "Creator: Actual message" in context


def test_build_chat_context_respects_character_limit(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()
    long_message = "x" * 500
    for i in range(20):
        llm._insert_chat_row("user", f"Message {i}: {long_message}")

    context = llm.build_chat_context()

    assert context is not None
    assert len(context) <= llm.CHAT_CONTEXT_MAX_CHARS


def test_build_chat_context_preserves_newest_messages_when_over_limit(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    """When the character limit is hit, the oldest messages are truncated but
    the newest ones survive."""
    configure_llm()
    llm._insert_chat_row("user", "First message")
    llm._insert_chat_row("user", "x" * 2000)
    llm._insert_chat_row("user", "y" * 2000)

    context = llm.build_chat_context()

    assert context is not None
    assert "Creator: y" in context
    assert "First message" not in context


def test_build_chat_context_skips_empty_messages(
    client: tuple[Any, Any], configure_llm: Any
) -> None:
    configure_llm()
    llm._insert_chat_row("user", "")
    llm._insert_chat_row("user", "   ")
    llm._insert_chat_row("mind", "Valid reply")

    assert llm.build_chat_context() == "Mind: Valid reply"
