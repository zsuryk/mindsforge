# Open-Source Pivot: OpenAI-Compatible LLMs and Vendor Removal

## Problem Statement

MindsForge was built for a Minds (Animoca Brands) hackathon. Every LLM capability — clip scoring, experiment winner decisions, adaptation feature manifests, chat, and memory — is hardwired to the Minds Builder API (`api.build.hellominds.ai`), gated behind credentials users can only get from the author. The project cannot be installed and run by anyone else, so it cannot be open-sourced as-is.

## Solution

Swap the Minds Builder integration for any OpenAI-compatible chat completions endpoint (OpenAI, Ollama, LM Studio, vLLM, OpenRouter, etc.), move the conversation thread and memory into local SQLite, rebrand vendor-specific surface text, and clean the repo of hackathon/vendor artifacts so it is publishable as an open-source project.

## User Stories

1. As a new user, I want to point the backend at my own OpenAI-compatible endpoint via `.env`, so that I can run MindsForge without Minds credentials.
2. As a user of Ollama/LM Studio, I want to set `OPENAI_BASE_URL` to my local server, so that I can run fully offline.
3. As a creator, I want clip scoring, experiment verdicts, and adaptations to work with my chosen model, so that the core pipeline functions end-to-end.
4. As a creator, I want chat history to persist across restarts, so that my conversation is not lost when the backend restarts.
5. As a creator, I want the "Mind's View" of memory and system notifications to behave as they do today, so that the Memory Inspector and dashboard still work.
6. As a developer, I want the same service-layer function signatures I mock in tests, so that the test suite ports with minimal churn.
7. As a user, I want the health endpoint to report my LLM backend status, so that I can confirm configuration.
8. As a user, I want the README to document any OpenAI-compatible provider, so that setup is self-serve.
9. As a contributor, I want no private Animoca npm packages in dependencies, so that `npm install` works with the public registry.
10. As a visitor, I want a LICENSE and no "contact me for keys" language, so that the repo reads as a real OSS project.
11. As a user, I want trend research to keep working with my `TAVILY_API_KEY`, so that chat grounding is unchanged.
12. As a developer, I want a single HTTP-layer seam for LLM mocking in tests, so that all service tests share one pattern.

## Implementation Decisions

### LLM client replaces the Minds service

A new module replaces `app/services/minds.py` and keeps its **public function names and signatures**: `generate_clip_metadata`, `decide_experiment_winner`, `generate_adaptation_features`, `send_chat_message`, `fetch_chat_history`, `build_chat_context`, `check_connection`, `fetch_memory`, `update_memory`, `notify_mind`, `post_chat_notification`. Callers in `pipeline.py`, `adaptations.py`, `ab_testing.py`, `trends.py`, and `app/api/chat.py` and `health.py` change only their import.

Configuration is via settings:

- `OPENAI_BASE_URL` (default `https://api.openai.com/v1`)
- `OPENAI_API_KEY` (empty allowed for local servers that ignore auth)
- `OPENAI_MODEL` (default e.g. `gpt-4o-mini`); a single model for all flows in v1
- Optional `OPENAI_TIMEOUT_SECONDS` (default 120)

The two-step prose-read → schema-fill prompt flow is preserved unchanged; `_parse_json_object` and the pydantic validation layer are reused. Conversation-alias isolation (`conversation_alias` parameters) becomes isolation by local thread/session id passed through the client.

Chat messages use the standard `messages: [{role, content}]` array; each call sends the rendered conversation context built from local SQLite (see below), not a remote history fetch.

### Conversation thread and memory move to SQLite

- New table `chat_messages` (id, role ∈ {user, assistant, system}, text, created_at, thread_id) replaces the remote `mindsforge-chat` conversation. Single default thread in v1.
- `notify_mind`/`post_chat_notification` insert a system row with the `[MindsForge] ` marker retained (UI strips it; ADR-0007 behavior preserved).
- `fetch_chat_history` reads the table newest→oldest→sorted, preserving the `ChatMessage` schema (`role: user|mind|system` — the "mind" role label may be renamed to "assistant" in the schema; frontend role filter is updated accordingly).
- `build_chat_context()` renders from SQLite with the same 4000-char cap and excludes the init instruction.
- `fetch_memory`/`update_memory` keep using `mind_memory` but key off a local thread/agent id constant instead of `MINDS_AGENT_ID`.
- A one-time init message (the existing `CHAT_INIT_INSTRUCTION`) is inserted into the thread when empty, replacing `_ensure_chat_initialised`.
- Alembic migration adds `chat_messages`.

### Fail-closed semantics preserved

ADR-0002's contract is kept: a scoring/experiment/adaptation failure because the LLM is unconfigured or errors fails that unit, with clear messages naming `OPENAI_API_KEY`/`OPENAI_BASE_URL` instead of the Minds keys. `check_connection` probes `GET {OPENAI_BASE_URL}/models` (or a tiny chat completion) and returns `unconfigured`/`ok`/`down`; the health endpoint field renames from `minds` to `llm`.

### Branding and docs

- Sidebar: drop "Powered by Minds / Persistent creator memory by Animoca Brands"; replace with neutral copy (e.g. "OpenAI-compatible LLM backend").
- `README.md`: rewrite prerequisites/config to OpenAI-compatible setup (OpenAI, Ollama, LM Studio examples); remove "contact for the Minds keys".
- `CONTEXT.md`: update the "Mind" gloss (now: the configured OpenAI-compatible model + local memory) and remove Animoca wording.
- ADRs: supersede 0002 (rename/retitle to "fail-closed LLM integration") and mark 0006 as superseded (Minds no longer owns memory; SQLite is the source of truth). ADR content can be edited in place with a supersedes note, matching existing style.
- `.env.example`: replace `MINDS_BUILDER_API_KEY`/`MINDS_AGENT_ID` with the new keys; keep `TAVILY_API_KEY`, Whisper, ffmpeg settings.
- Delete `@animocabrands/minds-cli` from `frontend/package.json` and regenerate `package-lock.json`.
- Remove `.hackathon/` from `.gitignore` relevance? Keep the ignore entry (harmless) but drop hackathon demo references from README.
- Add `LICENSE` (MIT) at repo root.

### Tests

- `backend/tests/test_minds.py` is renamed/reworked into tests for the new client module, mocking with `httpx.MockTransport` at the OpenAI HTTP layer (the established seam). Same coverage: two-step flows, JSON extraction tolerating fences, unknown-variant rejection, empty reasoning rejection, timeout/error mapping to the domain error type (`MindsError` renamed to `LLMError` with a `MindsError` alias during transition is NOT kept — callers and tests move to the new name; a final grep ensures no `minds` imports remain).
- All other backend tests keep mocking at the service-function boundary and remain nearly unchanged; import updates only.
- One migration test follows `test_migrations.py` prior art for `chat_messages`.

## Testing Decisions

- Good tests exercise external behavior through the service-function surface; HTTP-level (httpx `MockTransport`) mocking for LLM calls, service-function mocking for pipeline/API tests. Prior art: `backend/tests/test_minds.py`, `tests/conftest.py`.
- Modules under test: the new LLM client module, chat history/memory service functions, migrations, and (unchanged behavior) existing pipeline/adaptation/experiment tests.
- No new seams: reuse the HTTP seam for LLM traffic and the function-mock seam for everything above it.

## Out of Scope

- Supporting multiple models per flow, streaming chat UI, tool calling, or embeddings-based memory.
- Publishing/auto-posting integrations.
- Renaming the product (`mindsforge` name is kept).
- Migrating existing `mindsforge.db` chat history (there is no local chat history yet; remote Minds history is not imported).

## Further Notes

- `MINDS_AGENT_ID` concept is replaced by nothing — local thread id only.
- During transition, `SYSTEM_MARKER = "[MindsForge] "`, alias constants, and fingerprint logic are deleted with their module.
- Tavily trend research and Whisper transcription are unaffected.
