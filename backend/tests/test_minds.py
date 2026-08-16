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


# --- local memory store ---


def test_fetch_memory_returns_empty_tree_initially(
    client: tuple[Any, Any],
) -> None:
    assert minds.fetch_memory("agent-1") == {}


def test_update_memory_persists_key_value(client: tuple[Any, Any]) -> None:
    assert minds.update_memory("agent-1", "brand_voice", "bold") is True
    assert minds.fetch_memory("agent-1") == {"brand_voice": "bold"}


def test_update_memory_overwrites_existing_key(client: tuple[Any, Any]) -> None:
    minds.update_memory("agent-1", "k", 1)
    minds.update_memory("agent-1", "k", 2)
    assert minds.fetch_memory("agent-1") == {"k": 2}


def test_fetch_memory_is_scoped_by_agent_id(client: tuple[Any, Any]) -> None:
    minds.update_memory("agent-1", "k", "a")
    assert minds.fetch_memory("agent-2") == {}


def test_update_memory_stores_structured_values(client: tuple[Any, Any]) -> None:
    minds.update_memory("agent-1", "ab_test_history", [{"experiment_id": "e1"}])
    assert minds.fetch_memory("agent-1") == {
        "ab_test_history": [{"experiment_id": "e1"}]
    }


# --- messaging flow ---


def test_message_mind_sends_message_and_waits_for_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    posts: list[tuple[str, dict[str, Any]]] = []
    gets: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(path, payload):
        posts.append((path, payload))
        return FakeResponse({}, 200)

    def fake_get(path, params=None):
        gets.append((path, params))
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return FakeResponse([{"senderType": 0, "messageText": "hello reply"}], 200)

    monkeypatch.setattr(minds, "_post", fake_post)
    monkeypatch.setattr(minds, "_get", fake_get)

    reply = minds._message_mind("agent-1", "prompt text")

    assert reply == "hello reply"
    assert posts[0][0] == "/v1/messaging/conversation"
    assert posts[0][1] == {"alias": "mindsforge", "mindId": "agent-1"}
    assert posts[1][0] == "/v1/messaging/message"
    assert posts[1][1] == {"alias": "mindsforge", "messageText": "prompt text"}
    assert gets[1][0] == "/v1/messaging/histories/mindsforge"


def test_message_mind_ignores_human_echo_until_mind_replies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "_post", lambda path, payload: FakeResponse({}, 200))
    replies = [
        FakeResponse([{"senderType": 1, "messageText": "prompt text"}], 200),
        FakeResponse([{"senderType": 0, "messageText": "actual reply"}], 200),
    ]

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        return replies.pop(0)

    monkeypatch.setattr(minds, "_get", fake_get)

    assert minds._message_mind("agent-1", "prompt text") == "actual reply"


def test_message_mind_skips_stale_replies_older_than_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Builder history API ignores the `after` cursor, so the poll must
    filter client-side: a Mind reply that pre-dates the message we just sent
    is a stale reply to an earlier prompt and must not be returned."""
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "_post", lambda path, payload: FakeResponse({}, 200))

    stale_fp = "0001786721564254_stale-reply"
    echo_fp = "0001786725459810_echo"
    real_fp = "0001786725598305_real-reply"

    polls: list[list[dict[str, Any]]] = [
        [
            {"senderType": 1, "messageText": "prompt text", "fingerprint": echo_fp},
            {"senderType": 0, "messageText": "stale prose", "fingerprint": stale_fp},
        ],
        [
            {"senderType": 0, "messageText": "real reply", "fingerprint": real_fp},
            {"senderType": 1, "messageText": "prompt text", "fingerprint": echo_fp},
            {"senderType": 0, "messageText": "stale prose", "fingerprint": stale_fp},
        ],
    ]

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse(
                [{"senderType": 0, "messageText": "stale prose", "fingerprint": stale_fp}],
                200,
            )
        return FakeResponse(polls.pop(0), 200)

    monkeypatch.setattr(minds, "_get", fake_get)

    assert minds._message_mind("agent-1", "prompt text") == "real reply"


def test_message_mind_times_out_when_no_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "MESSAGE_REPLY_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(minds, "MESSAGE_REPLY_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(minds, "_post", lambda path, payload: FakeResponse({}, 200))
    monkeypatch.setattr(
        minds,
        "_get",
        lambda path, params=None: FakeResponse(
            [{"senderType": 1, "messageText": "prompt text"}], 200
        ),
    )

    with pytest.raises(minds.MindsError, match="Timed out"):
        minds._message_mind("agent-1", "prompt text")


class _FakeClock:
    """Deterministic clock: monotonic time advances only via sleep.

    Lets a test simulate a slow Mind reply (e.g. 335s of wall time) without
    actually sleeping, so the timeout boundary is exercised instantly.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_message_mind_accepts_reply_that_arrives_after_180s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Mind replies asynchronously and can take minutes; a reply landing
    after the (previously 180s) deadline must still be accepted, not reported
    as a timeout. Replays the real latency observed against the Builder API:
    prompt sent at t=0, prose read reply returned at t=335s."""
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "MESSAGE_REPLY_POLL_INTERVAL_SECONDS", 1.0)
    clock = _FakeClock()
    monkeypatch.setattr(minds.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(minds.time, "sleep", clock.sleep)
    monkeypatch.setattr(minds, "_post", lambda path, payload: FakeResponse({}, 200))

    prompt_fp = "0001786890817402_6514285c-47b1-4bba-8df2-347b"
    reply_fp = "0001786891152829_d9179f39-763a-4c54-955b-b403"

    def fake_get(path, params=None):
        if params and params.get("limit") == 1:
            return FakeResponse([], 200)
        if clock.now >= 335:
            return FakeResponse(
                [
                    {"senderType": 0, "messageText": "real read", "fingerprint": reply_fp},
                    {"senderType": 1, "messageText": "prompt text", "fingerprint": prompt_fp},
                ],
                200,
            )
        return FakeResponse(
            [{"senderType": 1, "messageText": "prompt text", "fingerprint": prompt_fp}], 200
        )

    monkeypatch.setattr(minds, "_get", fake_get)

    assert minds._message_mind("agent-1", "prompt text") == "real read"


def test_ensure_conversation_treats_alias_exists_as_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds,
        "_post",
        lambda path, payload: FakeResponse(
            {
                "error": {
                    "type": "BAD_INPUT",
                    "subType": "VALIDATION_FAILED",
                    "message": "alias already exists",
                }
            },
            400,
        ),
    )

    minds._ensure_conversation("agent-1")


def test_ensure_conversation_still_raises_on_other_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds,
        "_post",
        lambda path, payload: FakeResponse(
            {"error": {"type": "BAD_INPUT", "message": "bad mindId"}}, 400
        ),
    )

    with pytest.raises(minds.MindsError, match="Failed to create conversation"):
        minds._ensure_conversation("agent-1")


def test_headers_require_builder_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(minds.MindsConfigError, match="MINDS_BUILDER_API_KEY"):
        minds._headers()


def test_agent_id_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDS_BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("MINDS_AGENT_ID", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(minds.MindsConfigError, match="MINDS_AGENT_ID"):
        minds._agent_id()


# --- clip metadata generation ---


def test_generate_clip_metadata_parses_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            captured.update(agent_id=agent_id, prompt=prompt)
            or '{"virality_score": 82, "suggested_titles": ["A", "B"], '
            '"platform_hooks": {"youtube_shorts": ["s1"], "tiktok": ["t1"], "x": ["x1"]}}'
        ),
    )

    metadata = minds.generate_clip_metadata("hello world.", duration_seconds=21.5)

    assert metadata.virality_score == 82
    assert metadata.suggested_titles == ["A", "B"]
    assert metadata.platform_hooks["tiktok"] == ["t1"]
    assert captured["agent_id"] == "agent-1"
    assert "hello world." in captured["prompt"]
    assert "21.5s" in captured["prompt"]


def test_generate_clip_metadata_includes_memory_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            captured.update(prompt=prompt)
            or '{"virality_score": 50, "suggested_titles": ["A"], '
            '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}'
        ),
    )

    minds.generate_clip_metadata(
        "text", memory_context='brand_voice: "bold"\nhistorical_insights: []'
    )

    assert "brand_voice" in captured["prompt"]
    assert "historical_insights" in captured["prompt"]


def test_generate_clip_metadata_strips_markdown_fences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            '```json\n{"virality_score": 10, "suggested_titles": ["A"], '
            '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}\n```'
        ),
    )

    assert minds.generate_clip_metadata("text").virality_score == 10


def test_generate_clip_metadata_clamps_score_to_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            '{"virality_score": 150, "suggested_titles": ["A"], "platform_hooks": {}}'
        ),
    )

    assert minds.generate_clip_metadata("text").virality_score == 100


def test_generate_clip_metadata_raises_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds, "_message_mind", lambda agent_id, prompt, **kwargs: "not json at all"
    )
    with pytest.raises(minds.MindsError, match="no JSON object"):
        minds.generate_clip_metadata("text")


def test_generate_clip_metadata_refusal_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    refusal = (
        "<p>I'm not going to keep replying to the same template without hearing "
        "back from you, so let me say this once and plainly.</p>"
        "<p>This is the fourth templated prompt you've sent me - and the third "
        "copy…</p>"
    )
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: refusal)

    with pytest.raises(minds.MindsError) as excinfo:
        minds.generate_clip_metadata("text")

    message = str(excinfo.value)
    assert "substring not found" not in message
    assert "no JSON object" in message or "refus" in message.lower()


def test_generate_clip_metadata_uses_two_step_flow_when_read_is_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prose honest read is followed by a schema-fill message; the fill's
    JSON is parsed into the verdict."""
    _configure_minds(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            calls.append(prompt)
            or (
                "<p>Honest read: it's a two-decade-old meme, maybe 8/100.</p>"
                if len(calls) == 1
                else '{"virality_score": 8, "suggested_titles": ["A"], '
                '"platform_hooks": {"youtube_shorts": ["s1"], "tiktok": ["t1"], "x": ["x1"]}}'
            )
        ),
    )

    metadata = minds.generate_clip_metadata("hello world.")

    assert metadata.virality_score == 8
    assert len(calls) == 2
    assert "honest read" in calls[0].lower()
    assert '"virality_score"' in calls[1]
    assert "schema" in calls[1].lower()


def test_generate_clip_metadata_skips_fill_when_read_is_parseable_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            calls.append(prompt)
            or '{"virality_score": 42, "suggested_titles": ["A"], '
            '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}'
        ),
    )

    metadata = minds.generate_clip_metadata("text")

    assert metadata.virality_score == 42
    assert len(calls) == 1


def test_generate_clip_metadata_forwards_conversation_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    seen: dict[str, Any] = {}

    def fake_message_mind(agent_id, prompt, **kwargs):
        seen["agent_id"] = agent_id
        seen["alias"] = kwargs.get("alias")
        return (
            '{"virality_score": 5, "suggested_titles": ["A"], '
            '"platform_hooks": {"youtube_shorts": [], "tiktok": [], "x": []}}'
        )

    monkeypatch.setattr(minds, "_message_mind", fake_message_mind)

    minds.generate_clip_metadata("text", conversation_alias="mindsforge-job-abc")

    assert seen["agent_id"] == "agent-1"
    assert seen["alias"] == "mindsforge-job-abc"


def test_generate_clip_metadata_raises_on_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds, "_message_mind", lambda agent_id, prompt, **kwargs: '{"virality_score": 50}'
    )
    with pytest.raises(minds.MindsError, match="failed validation"):
        minds.generate_clip_metadata("text")


def test_generate_clip_metadata_raises_on_empty_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: "   ")
    with pytest.raises(minds.MindsError, match="missing 'response'"):
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
    assert 'creator_id: "creator-7"' in context
    assert 'brand_voice: "bold"' in context
    assert "historical_insights" in context
    assert "ab_test_history" in context


def test_build_memory_context_falls_back_to_whole_tree() -> None:
    context = minds.build_memory_context({"unexpected_key": {"nested": True}})
    assert "unexpected_key" in context
    assert context == '{"unexpected_key": {"nested": true}}'


VARIANTS = [
    {"variant_id": "v1", "title": "Hook A", "views": 600, "clicks": 30, "ctr": 5.0},
    {"variant_id": "v2", "title": "Hook B", "views": 400, "clicks": 8, "ctr": 2.0},
]


def test_decide_experiment_winner_parses_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            captured.update(prompt=prompt)
            or '{"winning_variant_id": "v1", "reasoning": "Hook A held viewers longer; reuse this formula."}'
        ),
    )

    verdict = minds.decide_experiment_winner(
        "youtube_shorts",
        VARIANTS,
        "the clip transcript",
        memory_context='brand_voice: "bold"',
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
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            '```json\n{"winning_variant_id": "v2", '
            '"reasoning": "debate-style hook won."}\n```'
        ),
    )
    assert minds.decide_experiment_winner("x", VARIANTS, "t").winning_variant_id == "v2"


def test_decide_experiment_winner_rejects_unknown_winner_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            '{"winning_variant_id": "ghost", "reasoning": "it felt right"}'
        ),
    )
    with pytest.raises(minds.MindsError, match="unknown variant id"):
        minds.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_rejects_empty_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: '{"winning_variant_id": "v1", "reasoning": "   "}',
    )
    with pytest.raises(minds.MindsError, match="failed validation"):
        minds.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


def test_decide_experiment_winner_raises_on_empty_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: "  ")
    with pytest.raises(minds.MindsError, match="missing 'response'"):
        minds.decide_experiment_winner("youtube_shorts", VARIANTS, "t")


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


def test_generate_adaptation_features_parses_long_form_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            captured.update(prompt=prompt) or _youtube_long_form_reply()
        ),
    )

    manifest = minds.generate_adaptation_features(
        CLIP, "youtube", "LONG_FORM", SEGMENTS, memory_context='brand_voice: "bold"'
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
    _configure_minds(monkeypatch)
    echoed = _youtube_long_form_reply().replace(
        '{"chapters"', '{"surface": "LONG_FORM", "chapters"', 1
    )
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: echoed)
    manifest = minds.generate_adaptation_features(
        CLIP, "youtube", "LONG_FORM", SEGMENTS
    )
    assert manifest.surface == "LONG_FORM"


def test_generate_adaptation_features_rejects_surface_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    echoed = _youtube_long_form_reply().replace(
        '{"chapters"', '{"surface": "SHORTS", "chapters"', 1
    )
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: echoed)
    with pytest.raises(minds.MindsError, match="expected 'LONG_FORM'"):
        minds.generate_adaptation_features(CLIP, "youtube", "LONG_FORM", SEGMENTS)


def test_generate_adaptation_features_enforces_three_thumbnail_briefs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    reply = (
        '{"thumbnail_briefs": ['
        '{"frame_timestamp": 3.0, "overlay_text": "one"}, '
        '{"frame_timestamp": 4.0, "overlay_text": "two"}], '
        '"platform_hooks": ["hook"]}'
    )
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: reply)
    with pytest.raises(minds.MindsError, match="exactly 3 thumbnail_briefs"):
        minds.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)


def test_generate_adaptation_features_validates_tiktok_post_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            '{"overlay_spec": [{"text": "t", "placement": "center", "style": "bold"}]}'
        ),
    )
    with pytest.raises(minds.MindsError, match="requires caption_style"):
        minds.generate_adaptation_features(CLIP, "tiktok", "POST", SEGMENTS)


def test_generate_adaptation_features_requires_x_caption_and_hashtags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds, "_message_mind", lambda agent_id, prompt, **kwargs: '{"caption": "hot take"}'
    )
    with pytest.raises(minds.MindsError, match="requires hashtags"):
        minds.generate_adaptation_features(CLIP, "x", "POST", SEGMENTS)


def test_generate_adaptation_features_uses_two_step_flow_when_read_is_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prose read (the Mind refusing the single-shot JSON shape) is followed
    by a schema-fill message; the fill's JSON is parsed into the manifest."""
    _configure_minds(monkeypatch)
    calls: list[str] = []
    refusal = (
        "<p>Hey - seventeenth round, new prompt shape. Same lane issues with "
        "three new wrinkles, and the clip is real so I'll engage the parts I "
        "can engage honestly.</p>"
        "<p>Three flags on the prompt before any { real engagement } happens... "
        "the shape demands a fabricated manifest.</p>"
    )
    monkeypatch.setattr(
        minds,
        "_message_mind",
        lambda agent_id, prompt, **kwargs: (
            calls.append(prompt)
            or (refusal if len(calls) == 1 else _youtube_long_form_reply())
        ),
    )

    manifest = minds.generate_adaptation_features(
        CLIP, "youtube", "LONG_FORM", SEGMENTS, memory_context='brand_voice: "bold"'
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
    _configure_minds(monkeypatch)
    refusal = (
        "<p>the clip is real so I'll engage the parts I can engage honestly "
        "{ not a manifest }</p>"
    )
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: refusal)

    with pytest.raises(minds.MindsError) as excinfo:
        minds.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)

    message = str(excinfo.value)
    assert "Expecting value" not in message
    assert "no JSON object" in message or "refus" in message.lower()


def test_generate_adaptation_features_forwards_conversation_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    seen: dict[str, Any] = {}

    def fake_message_mind(agent_id, prompt, **kwargs):
        seen["agent_id"] = agent_id
        seen["alias"] = kwargs.get("alias")
        return _youtube_long_form_reply()

    monkeypatch.setattr(minds, "_message_mind", fake_message_mind)

    minds.generate_adaptation_features(
        CLIP,
        "youtube",
        "LONG_FORM",
        SEGMENTS,
        conversation_alias="mindsforge-adapt-abc",
    )

    assert seen["agent_id"] == "agent-1"
    assert seen["alias"] == "mindsforge-adapt-abc"


def test_generate_adaptation_features_raises_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: "not json")
    with pytest.raises(minds.MindsError, match="no JSON object"):
        minds.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)


def test_generate_adaptation_features_raises_on_empty_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(minds, "_message_mind", lambda agent_id, prompt, **kwargs: "")
    with pytest.raises(minds.MindsError, match="missing 'response'"):
        minds.generate_adaptation_features(CLIP, "youtube", "SHORTS", SEGMENTS)


def test_network_errors_are_wrapped_as_minds_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_minds(monkeypatch)
    monkeypatch.setattr(
        minds.httpx,
        "post",
        lambda url, headers, json, timeout: (_ for _ in ()).throw(
            httpx.TimeoutException("timed out")
        ),
    )
    with pytest.raises(minds.MindsError, match="timed out"):
        minds._post("/v1/messaging/message", {})
