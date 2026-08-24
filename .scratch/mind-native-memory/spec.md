# Mind-Native Memory: Shift from SQLite Sidecar to Mind-Owned Memory

## Problem Statement

MindsForge currently uses a SQLite sidecar (`mind_memory` table) as the primary intelligence layer for memory. The Mind's native conversation thread is only used for chat responses — all generation prompts (scoring, adaptation, experiment conclusion) are driven by SQLite data rendered via `build_memory_context()`. A Groq LLM sidecar extracts brand rules from chat messages and persists them to SQLite.

This architecture duplicates what the Mind does natively. For a hackathon organized by Minds, judges expect to see the Mind itself own and drive memory. The current design positions MindsForge as an app that happens to use Minds as an API endpoint, rather than a Minds-native app.

## Solution

Shift the balance so the Mind's conversation thread becomes the authoritative memory. SQLite becomes a transparent backing store for UI features (Memory Inspector), not the intelligence layer. The Groq brand-rule extraction sidecar is removed entirely — the Mind natively captures and acknowledges creator preferences from its conversation context. Generation prompts are fed the Mind's own conversation thread as context, so every decision is grounded in what the Mind itself has seen and learned.

## User Stories

1. As a creator, I want the Mind to remember my brand rules from our chat conversations, so that every clip scoring and adaptation reflects my preferences without me repeating them.
2. As a creator, I want the Mind to reference past experiment results when generating new adaptations, so that it learns from what worked and what didn't.
3. As a creator, I want the Mind to acknowledge when it saves a preference ("I'll remember that always use bold captions"), so that I trust the memory is working.
4. As a creator, I want to see what the Mind remembers in the Memory Inspector, including both the raw conversation thread and the structured cache.
5. As a creator, I want to see a "Mind remembers" indicator on clips and adaptations showing which of my past rules influenced the output.
6. As a creator, I want clip scoring to be grounded in my brand voice and past learnings, so that scores reflect my audience and style, not generic virality.
7. As a creator, I want adaptation generation to use my brand rules and trend research, so that hooks, captions, and tags are on-brand and timely.
8. As a creator, I want experiment conclusions to consider my past learnings, so that the Mind builds on prior knowledge rather than starting fresh each time.
9. As a developer, I want the Groq dependency removed, so that the system has fewer moving parts and simpler failure modes.
10. As a developer, I want the init instruction to prime the Mind to actively reference its memory, so that the Mind demonstrates persistence in every interaction.

## Implementation Decisions

### Context injection: conversation thread replaces SQLite rendering

The `build_memory_context()` function (which renders SQLite key/value pairs into a text block) is replaced by a new `build_chat_context()` function. This function:
- Fetches the `mindsforge-chat` conversation thread via the existing `_history_rows()` function
- Filters to meaningful messages: creator messages, Mind replies, and system notifications
- Renders them as a role-annotated text block (e.g., "Creator: ...", "Mind: ...", "[System] ...")
- Caps the output at ~4000 characters to stay within prompt token budgets
- Excludes the system initialization instruction (it's setup, not memory)

This context is injected into three generation flows:
1. **Clip scoring** (`pipeline.py:_score_clips()`): replaces the `memory_context` parameter in `generate_clip_metadata()`
2. **Adaptation generation** (`adaptations.py:_memory_context()`): replaces the SQLite memory fetch, but keeps the curated trend block (trend results are already in the chat thread as system notifications, so the block becomes a filtered view of those notifications)
3. **Experiment conclusion** (`ab_testing.py:_conclude_experiment()`): replaces the SQLite memory fetch

The two-step prompt flow (read → fill) is unchanged. The conversation context is prepended to the read prompt.

### Brand-rule extraction: trust the Mind

The Groq sidecar (`rules.py`) is deleted entirely. The `CHAT_INIT_INSTRUCTION` is strengthened to explicitly tell the Mind to acknowledge and remember brand rules. The Mind's native conversation memory handles extraction — when a creator says "always use bold captions", the Mind acknowledges it in its reply and retains it in its conversation context.

The `send_chat_message()` endpoint no longer calls `extract_and_persist_brand_rules()`. The `ChatSendOut` response schema drops the `rules` field (the UI confirmation chip for saved rules is removed or replaced with the Mind's natural acknowledgment in its reply).

### Memory Inspector: dual-view

The Memory Inspector page retains the existing SQLite raw context view (useful for debugging) and adds a new "Mind's View" section that shows the conversation thread. This demonstrates to judges that the Mind's native memory is the primary system.

The "Mind's View" section uses the existing `GET /api/v1/chat/history` endpoint. Messages are rendered with role annotations (creator, Mind, system).

### "Mind remembers" badge

A new component displays which brand rules from the conversation were active when a clip was scored or an adaptation was generated. Implementation: parse brand rules from the conversation thread (messages containing creator preference statements), display as chips on clip/adaptation cards.

### Init instruction update

The `CHAT_INIT_INSTRUCTION` is updated to include: "When you score clips or generate adaptations, explicitly reference what you remember about this creator's preferences and past results. Reference specific rules and experiments when they are relevant."

## Testing Decisions

- Test the `build_chat_context()` function: given a mock conversation history, verify it renders correctly, handles empty history, respects the character limit, and filters out the init instruction.
- Test that `send_chat_message()` no longer calls Groq (mock the Groq client and assert it's not called).
- Test the Memory Inspector UI renders the conversation thread section.
- Test the "Mind remembers" badge correctly parses brand rules from conversation history.
- Prior art: existing `test_rules.py` tests for brand-rule extraction (to be deleted or rewritten), `api.test.ts` for chat API tests.

## Out of Scope

- Changing the scoring/adaptation prompt templates (beyond adding conversation context)
- Modifying the Minds Builder API integration (conversation aliases, message polling, etc.)
- The Memory Inspector's "Write to memory" functionality (retained as-is)
- The A/B testing simulation engine (unchanged)
- Frontend chat UI changes beyond removing the rules confirmation chip

## Further Notes

The `MEMORY_CONTEXT_KEYS` constant and `build_memory_context()` function become dead code after this change and should be removed. The `memory_context` parameter in `generate_clip_metadata()`, `generate_adaptation_features()`, and `decide_experiment_winner()` should be renamed to `chat_context` for clarity, though the prompts that consume it can stay largely the same — just swapping the "Creator memory context" header for "Creator conversation context".

The trend research flow is unaffected: Tavily search results are already posted as system notifications to the chat thread, so they naturally appear in the conversation context. The curated `build_trend_block()` function can be simplified to filter chat notifications rather than SQLite data.
