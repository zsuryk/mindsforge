# 02: OpenAI-compatible client for scoring and adaptations

**What to build:** A new LLM client module configured by `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, and timeout settings, calling the standard chat completions endpoint with the existing two-step prose-read → schema-fill prompt flow. Clip scoring and adaptation generation switch to it. Fail-closed semantics from ADR-0002 are preserved: unconfigured/errored LLM fails the job with a clear message.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Pipeline clip scoring (`generate_clip_metadata`) works end-to-end against an OpenAI-compatible endpoint
- [ ] Adaptation generation (`generate_adaptation_features`) works end-to-end with the same client
- [ ] JSON extraction tolerates fences; pydantic manifest validation failures surface as the domain error
- [ ] Missing `OPENAI_API_KEY` (when required) or network failure produces a clear error, not a silent fallback
- [ ] Health endpoint still answers; LLM status probe for the new backend is stubbed or deferred to ticket 04
