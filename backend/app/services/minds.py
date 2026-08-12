import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError, field_validator

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MINDS_BUILDER_BASE_URL = "https://build.hellominds.ai/api/v1"
BUILDER_API_KEY_HEADER = "X-Api-Key"
HTTP_TIMEOUT_SECONDS = 30.0

MEMORY_CONTEXT_KEYS = ("creator_id", "brand_voice", "historical_insights", "ab_test_history")
MEMORY_CONTEXT_VALUE_LIMIT = 2000


class MindsError(RuntimeError):
    pass


class MindsConfigError(MindsError):
    """Raised when Minds credentials are missing from configuration."""


class ClipMetadata(BaseModel):
    """Structured verdict returned by the Mind for a single clip."""

    virality_score: int
    suggested_titles: list[str]
    platform_hooks: dict[str, list[str]]

    @field_validator("virality_score")
    @classmethod
    def _clamp_score(cls, value: int) -> int:
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError) as exc:
            raise ValueError("virality_score must be an integer") from exc


class ExperimentVerdict(BaseModel):
    """Structured verdict returned by the Mind at experiment conclusion."""

    winning_variant_id: str
    reasoning: str

    @field_validator("reasoning")
    @classmethod
    def _require_reasoning(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("reasoning must not be empty")
        return value


def _headers() -> dict[str, str]:
    key = get_settings().MINDS_BUILDER_API_KEY
    if not key:
        raise MindsConfigError("MINDS_BUILDER_API_KEY is not configured")
    return {BUILDER_API_KEY_HEADER: key}


def _agent_id() -> str:
    agent_id = get_settings().MINDS_AGENT_ID
    if not agent_id:
        raise MindsConfigError("MINDS_AGENT_ID is not configured")
    return agent_id


def _decode_json(response: httpx.Response, context: str) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise MindsError(f"{context} returned a non-JSON response") from exc


def _get(path: str) -> httpx.Response:
    try:
        response = httpx.get(
            f"{MINDS_BUILDER_BASE_URL}{path}",
            headers=_headers(),
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise MindsError(f"Builder API request failed: {exc}") from exc
    return response


def _post(path: str, payload: dict[str, Any]) -> httpx.Response:
    try:
        response = httpx.post(
            f"{MINDS_BUILDER_BASE_URL}{path}",
            headers=_headers(),
            json=payload,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise MindsError(f"Builder API request failed: {exc}") from exc
    return response


def fetch_memory(agent_id: str) -> dict[str, Any]:
    """Fetch the Mind's context tree (`GET /minds/{agent_id}/memory`)."""
    response = _get(f"/minds/{agent_id}/memory")
    if response.status_code != 200:
        raise MindsError(f"Memory fetch failed with status {response.status_code}")
    memory = _decode_json(response, "Memory fetch")
    if not isinstance(memory, dict):
        raise MindsError("Memory fetch returned an unexpected shape")
    return memory


def update_memory(agent_id: str, key: str, value: Any) -> bool:
    """Persist an insight key/value on the Mind (`POST /minds/{agent_id}/memory/update`)."""
    response = _post(f"/minds/{agent_id}/memory/update", {"key": key, "value": value})
    if response.status_code != 200:
        raise MindsError(f"Memory update failed with status {response.status_code}")
    payload = _decode_json(response, "Memory update")
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("success"))


def build_memory_context(memory: dict[str, Any]) -> str:
    """Render the memory context tree as a compact prompt fragment."""
    lines: list[str] = []
    for key in MEMORY_CONTEXT_KEYS:
        value = memory.get(key)
        if value is None:
            continue
        rendered = json.dumps(value, ensure_ascii=False)
        if len(rendered) > MEMORY_CONTEXT_VALUE_LIMIT:
            rendered = f"{rendered[:MEMORY_CONTEXT_VALUE_LIMIT]}…"
        lines.append(f"{key}: {rendered}")
    if lines:
        return "\n".join(lines)
    rendered = json.dumps(memory, ensure_ascii=False)
    if len(rendered) > MEMORY_CONTEXT_VALUE_LIMIT:
        rendered = f"{rendered[:MEMORY_CONTEXT_VALUE_LIMIT]}…"
    return rendered


def _build_metadata_prompt(
    transcript: str,
    *,
    duration_seconds: float | None,
    memory_context: str | None,
) -> str:
    memory_block = memory_context if memory_context else "none"
    duration_block = f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown"
    return (
        "You are a short-form content strategist working with a creator. "
        "Score the clip transcript below and produce platform-specific hooks.\n\n"
        f"Clip transcript:\n{transcript}\n\n"
        f"Clip duration: {duration_block}\n\n"
        "Creator memory context (historical insights):\n"
        f"{memory_block}\n\n"
        'Respond with ONLY a JSON object, no markdown fences, with exactly this shape:\n'
        '{\n'
        '  "virality_score": 0-100 integer,\n'
        '  "suggested_titles": ["3-5 short titles under 70 characters"],\n'
        '  "platform_hooks": {\n'
        '    "youtube_shorts": ["3-5 hooks"],\n'
        '    "tiktok": ["3-5 hooks"],\n'
        '    "x": ["3-5 hooks"]\n'
        '  }\n'
        '}\n'
        "Rules:\n"
        "- virality_score reflects this clip's engagement potential for this creator.\n"
        "- suggested_titles: hook-driven titles, each under 70 characters.\n"
        "- platform_hooks: tailor each set to the platform's style — YouTube Shorts: "
        "curiosity and retention; TikTok: trend-aware, first-frame hooks; "
        "X: text-first, opinionated or debate-style hooks."
    )


def _parse_json_object(text: str, context: str) -> dict[str, Any]:
    """Extract the first JSON object from a model reply, tolerating fences."""
    if text.startswith("```"):
        fenced = text.split("```", 2)
        if len(fenced) >= 2:
            text = fenced[1].removeprefix("json").strip()
    try:
        start, end = text.index("{"), text.rindex("}")
        data = json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError) as exc:
        raise MindsError(f"Could not parse {context} JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MindsError(f"{context} returned a non-object body")
    return data


def _parse_metadata(message: str) -> ClipMetadata:
    data = _parse_json_object(message, "clip metadata")
    try:
        return ClipMetadata(**data)
    except ValidationError as exc:
        raise MindsError(f"Clip metadata failed validation: {exc}") from exc


def generate_clip_metadata(
    transcript: str,
    *,
    duration_seconds: float | None = None,
    memory_context: str | None = None,
) -> ClipMetadata:
    """Prompt the Mind to score a clip and return the structured verdict.

    Raises MindsError on any failure (missing credentials, HTTP errors,
    unparseable or invalid responses) so callers can degrade gracefully.
    """
    prompt = _build_metadata_prompt(
        transcript, duration_seconds=duration_seconds, memory_context=memory_context
    )
    response = _post(f"/minds/{_agent_id()}/message", {"prompt": prompt})
    if response.status_code != 200:
        raise MindsError(
            f"Clip metadata generation failed with status {response.status_code}"
        )
    message = response.json().get("response")
    if not isinstance(message, str) or not message.strip():
        raise MindsError("Clip metadata response missing 'response' text")
    return _parse_metadata(message)


def _build_winner_prompt(
    platform: str,
    variants: list[dict[str, Any]],
    transcript: str,
    memory_context: str | None,
) -> str:
    memory_block = memory_context if memory_context else "none"
    variant_lines = "\n".join(
        f"- variant_id: {variant.get('variant_id')}, "
        f"title: {variant.get('title', '')}, "
        f"views: {variant.get('views', 0)}, "
        f"clicks: {variant.get('clicks', 0)}, "
        f"ctr: {variant.get('ctr', 0.0)}%"
        for variant in variants
    )
    return (
        "You are an A/B testing analyst working with a creator. "
        "An experiment on one of the creator's clips just crossed its view "
        "threshold; study the variants and the clip transcript, then pick the "
        "winning variant and explain why.\n\n"
        f"Platform: {platform}\n\n"
        f"Clip transcript:\n{transcript}\n\n"
        "Experiment variants:\n"
        f"{variant_lines}\n\n"
        "Creator memory context (brand voice and past learnings):\n"
        f"{memory_block}\n\n"
        'Respond with ONLY a JSON object, no markdown fences, with exactly this shape:\n'
        '{\n'
        '  "winning_variant_id": "the id of the winning variant from the list above",\n'
        '  "reasoning": "2-3 sentences: why this variant won and what to reuse next time"\n'
        '}\n'
        "Rules:\n"
        "- winning_variant_id must exactly match one of the variant_id values above.\n"
        "- reasoning must be non-empty and grounded in the variant metrics and clip content.\n"
        "- The reasoning doubles as the lesson persisted to the creator's memory."
    )


def _parse_winner_verdict(message: str) -> ExperimentVerdict:
    data = _parse_json_object(message, "experiment verdict")
    try:
        return ExperimentVerdict(**data)
    except ValidationError as exc:
        raise MindsError(f"Experiment verdict failed validation: {exc}") from exc


def decide_experiment_winner(
    platform: str,
    variants: list[dict[str, Any]],
    transcript: str,
    *,
    memory_context: str | None = None,
) -> ExperimentVerdict:
    """Ask the Mind to pick the winning variant of a concluded experiment.

    Raises MindsError on any failure (missing credentials, HTTP errors,
    unparseable verdicts, unknown winner ids, empty reasoning) so callers
    can fail the experiment closed instead of falling back to metrics.
    """
    prompt = _build_winner_prompt(platform, variants, transcript, memory_context)
    response = _post(f"/minds/{_agent_id()}/message", {"prompt": prompt})
    if response.status_code != 200:
        raise MindsError(
            f"Experiment winner decision failed with status {response.status_code}"
        )
    message = response.json().get("response")
    if not isinstance(message, str) or not message.strip():
        raise MindsError("Experiment verdict response missing 'response' text")
    verdict = _parse_winner_verdict(message)
    known_ids = {str(variant.get("variant_id")) for variant in variants if variant.get("variant_id")}
    if not known_ids or verdict.winning_variant_id not in known_ids:
        raise MindsError(
            f"Experiment verdict picked unknown variant id {verdict.winning_variant_id!r}"
        )
    return verdict
