# 15 — Creator chat: Mind messaging backend

**What to build:** The backend of the creator-facing Chat. `POST /chat/messages`
sends a message to the Mind over the messaging API on a dedicated
`mindsforge-chat` conversation and returns the Mind's reply; `GET /chat/history`
returns the thread with roles (user / mind / system) for the UI. The chat
conversation is native Minds persistence — the Mind remembers the thread
across sessions, so no app-side chat storage exists.

**Blocked by:** none

**Status:** ready-for-agent

## Problem Statement

The Mind's messaging API supports multi-turn conversation (one alias = one
conversation, POST a message, poll history for senderType-0 replies), but every
current call site uses the shared `mindsforge` alias with a 600s timeout tuned
for long structured prompts. Chat needs its own conversation, a fast reply
timeout, history loading, and a way to distinguish the app's own messages
(notifications, trend results) from the creator's messages in the thread.

## Solution

- New constant `CHAT_ALIAS = "mindsforge-chat"` — chat never mixes with
  scoring/adaptation conversations (which keep `MESSAGING_ALIAS` and their
  per-attempt aliases).
- `minds.send_chat_message(text) -> str`: ensure the conversation, cursor =
  latest history fingerprint, POST `/v1/messaging/message`, poll every 2s for
  the first Mind reply (senderType 0) newer than the cursor.
  `CHAT_REPLY_TIMEOUT_SECONDS = 180` — chat messages are short and replies were
  measured at ~15s; a hung reply fails fast instead of stalling the demo.
  Reuses the existing `_ensure_conversation` / `_message_mind` machinery
  (refactor `_message_mind` to take a timeout parameter rather than duplicating
  the poll loop).
- `minds.fetch_chat_history(limit=50) -> list[ChatMessage]` with
  `ChatMessage{role: "user" | "mind" | "system", text, fingerprint}`:
  senderType 0 → "mind"; senderType 1 with the system marker → "system" with
  the marker stripped; senderType 1 otherwise → "user".
- System-marker convention: the app's own messages (notifications, trend
  results, initialisation) are posted as senderType-1 messages prefixed with
  `SYSTEM_MARKER = "[MindsForge] "`. The Mind reads them as normal content; the
  UI renders them as system chips and strips the prefix.
- Initialisation: when `POST /chat/messages` finds the conversation empty (no
  history rows), post one system-marked instruction before the first user
  message: the Mind is the creator's content strategist, grounded in the
  conversation and its memory, acknowledges brand rules the creator states,
  and may use its own Tavily connection to research trends when asked.
- `POST /chat/messages {message}` → `200 {reply, rules: []}`. `rules` is the
  ticket-17 seam (empty until then). Minds unconfigured or any MindsError →
  `502` with the clear message (fail-closed per ADR-0002; no silent fallback
  text).
- `GET /chat/history` → `200 {messages: [...]}`; unconfigured Minds → `502`.
- Reply-attribution edge case (documented, accepted): a background
  notification (ticket 18) may post while a reply is awaited; the endpoint
  returns the first Mind reply newer than the cursor, and the UI polls the full
  history so any mis-attributed acknowledgment self-corrects in the thread.

## User Stories

1. As a creator, I want to send a message to my Mind and get its reply in about
   the time of a normal chat, so I can talk to it like a collaborator.
2. As a creator, I want to reload the chat page and see the whole conversation,
   so I never lose the thread between sessions.
3. As a developer, I want chat traffic isolated from scoring traffic, so a
   long structured prompt can never pollute or stall the chat conversation.

## Implementation Decisions

- Refactor `_message_mind` to accept `timeout_seconds` (default keeps 600s for
  scoring); `send_chat_message` passes 180.
- `CHAT_ALIAS`, `SYSTEM_MARKER`, `ChatMessage` and the two functions live in
  `app/services/minds.py`; the HTTP endpoints live in a new
  `app/api/chat.py` router registered in `main.py`.
- No local chat table: the conversation is the Minds-side history, which is
  the native persistence this product is demonstrating.
- The initialisation instruction posts only when the conversation is empty, so
  it never repeats.

## Testing Decisions

- New `backend/tests/test_chat.py` using the existing fake-Minds seams
  (`test_minds.py` prior art):
  - happy path: send → reply text returned; message sent to `mindsforge-chat`
    alias, never `mindsforge`.
  - timeout: no Mind reply within the (monkeypatched-short) timeout → MindsError
    → API 502 with message.
  - history mapping: senderType 0 → mind, marked senderType 1 → system with
    marker stripped, unmarked senderType 1 → user.
  - initialisation: empty conversation posts the instruction before the first
    message; a non-empty conversation does not.
  - unconfigured Minds → 502 for both endpoints.
  - `rules` is `[]` until ticket 17 lands.
- Existing tests keep passing (the refactor of `_message_mind` must not change
  scoring behaviour).

## Out of Scope

- The `/chat` frontend page (ticket 19).
- Trend search and brand-rule extraction (tickets 16, 17).
- Mind notifications (ticket 18).
- Streaming replies — the messaging API is poll-based by design.

## Further Notes

Commit on `main` as a single conventional `feat(chat): …` commit.