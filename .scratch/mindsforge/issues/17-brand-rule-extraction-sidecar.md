# 17 — Brand-rule extraction sidecar

**What to build:** Detect brand-rule statements in chat messages and persist
them to the Mind's memory. A fast Groq extraction call inspects each user
message for explicit creator preferences, appends them to a new `brand_rules`
memory key, and returns them with the chat response so the UI can show a
"saved to your Mind" chip. The rules become part of the memory context every
generation prompt already receives.

**Blocked by:** 15 (hooks into `POST /chat/messages`)

**Status:** ready-for-agent

## Problem Statement

The chat Mind remembers rules natively from the conversation, but the
generation pipeline cannot read the Mind's native memory — it consumes the
app-side memory tree (SQLite) injected as prompt context. Rules stated in
chat must be captured in machine-readable form and written to that tree, or
they will never shape hooks, captions, and adaptations. The Mind's freeform
replies cannot be parsed reliably, so detection happens app-side.

## Solution

- New `app/services/rules.py`:
  - `extract_brand_rules(message) -> list[BrandRule]` where
    `BrandRule{text, platform?}`. Uses the existing Groq SDK with
    `GROQ_API_KEY` (already configured); default model
    `llama-3.3-70b-versatile` (verify availability at build time and adjust).
    Structured JSON verdict `{rules: [...]}` or `{rules: []}`.
  - Strict extraction prompt: only explicit creator preference statements
    ("always use bold captions", "my audience is beginners", "never
    clickbait", "post shorts daily"); ignore questions, opinions, and
    statements about the clip being discussed.
- `POST /chat/messages` runs extraction on the user message and returns
  `{reply, rules: [...]}` (the ticket-15 seam fills in). Detected rules are
  appended to the `brand_rules` memory key as
  `{text, platform?, created_at, source: "chat"}`; the list is bounded to the
  last 50 entries; an empty verdict is a no-op.
- Extraction failure is non-blocking: the message still reaches the Mind and
  `rules: []` is returned (sidecar, not a gate — the Mind itself still read
  the statement in the thread). Failure is logged.
- `MEMORY_CONTEXT_KEYS` in `minds.py` gains `"brand_rules"` — every prompt
  that already receives memory context (clip scoring, adaptation generation,
  experiment winner decision) automatically carries the creator's rules.

## User Stories

1. As a creator, I want my Mind to record my stated preferences and apply
   them to everything it generates from then on, so I never repeat myself.
2. As a creator, I want visible confirmation when a rule is saved, so I trust
   the memory actually persists.
3. As an operator, I want extraction failures to never block the chat, so the
   Mind's conversation stays available when a sidecar degrades.

## Implementation Decisions

- Extraction runs on every user message (not batched): chat volume is low and
  the cost is negligible; immediacy makes the "saved" chip feel live.
- Rules live under a structured `brand_rules` key, separate from freeform
  `brand_voice`; both are injected (grilled decision).
- No Mind notification for saved rules: the creator's statement is already in
  the thread the Mind reads natively; a redundant notification would spam the
  Mind (documented in ticket 18).

## Testing Decisions

- New `backend/tests/test_rules.py`:
  - extraction happy path (stubbed Groq) → structured rules list;
  - no preference detected → `[]` and no memory write;
  - extraction failure → message still sent, `rules: []`, warning logged;
  - `brand_rules` appends and is bounded to 50;
  - `brand_rules` appears in `build_memory_context` output and in the
    adaptation read prompt.
- `backend/tests/test_chat.py` (ticket 15) extended: the `rules` field is
  populated by the sidecar seam.
- Existing tests stay green (no brand rules → no prompt change).

## Out of Scope

- Rule editing/deletion UI (the Memory Inspector "Write to memory" form
  already offers manual management).
- Extracting rules from Mind replies (the Mind is the advisor, not the
  decision-maker on what the creator wants).
- Writing rules to the Mind's platform-native memory (unreadable by the app).

## Further Notes

Commit on `main` as a single conventional `feat(chat): …` commit.