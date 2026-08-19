# 19 — Chat frontend

**What to build:** The `/chat` page: a full chat UI with the Mind. Thread
rendering (user bubbles, Mind replies, system chips, rule-saved chips, trend
chips), a message input, a "Research trends" affordance, a "your Mind is
thinking…" state, and history polling so background notifications and late
replies always surface.

**Blocked by:** 15, 16, 17 (backend messaging, trends, rules)

**Status:** ready-for-agent

## Problem Statement

The chat backend exists but nothing renders it. The chat is the flagship
Minds-integrality demo for the hackathon (conversation with the Mind, native
memory, visible persistence), so the UI must be as polished as the rest of
the Linear-style design system.

## Solution

- New route `/chat` + sidebar item ("Chat", `MessageCircle` icon) in
  `sidebar.tsx`.
- `frontend/lib/api.ts` additions:
  - `ChatMessage{role: "user" | "mind" | "system", text, fingerprint}`
  - `sendChatMessage(message) -> {reply, rules: [{text, platform?}]}`
  - `fetchChatHistory() -> {messages: ChatMessage[]}`
  - `researchTrends(query) -> {results: [{title, url, content}]}`
- Chat page (`frontend/app/chat/page.tsx` + components):
  - On mount: `fetchChatHistory` and render the thread — user messages
    right-aligned, Mind messages left-aligned, system messages as compact
    chips (marker already stripped by the backend).
  - Send flow: optimistic user bubble → `sendChatMessage` → append the reply
    when it returns; "Your Mind is thinking…" indicator while awaiting.
  - While a reply is pending, and after it lands, poll `fetchChatHistory`
    every 5s: this catches notifications and Mind acknowledgments (ticket 18)
    and self-corrects the attribution edge case (ticket 15).
  - Rule chips: when `sendChatMessage` returns `rules`, render a small
    "Your Mind saved: <text>" chip under the user message.
  - Trend research: an input + "Research trends" button; on success render a
    chip listing the top results; the button posts `researchTrends` and the
    user can then message the Mind about them.
  - Error state: `502` bodies (Minds or Tavily unconfigured) render as a
    banner with the backend's message — never a silent failure.
  - Empty state: no history → welcome copy pointing at the demo flow ("Tell
    your Mind a brand rule, or ask it to research a trend").
- Styling follows the existing design system (dark `bg-slate-950` base,
  shadcn primitives, the `font-display`/`text-subtle` vocabulary).

## User Stories

1. As a creator, I want a chat page that looks and feels like a real
   messaging app, so talking to my Mind is natural.
2. As a creator, I want to see, inline, what my Mind saved to memory and what
   trends it researched, so the persistence story is visible without leaving
   the page.
3. As a creator, I want the page to keep showing the thread fresh (including
   background notifications), so I never miss something my Mind was told.

## Implementation Decisions

- Polling over WebSockets: the backend has no WS infra and the existing
  `WS_URL` is unused; a 5s poll is consistent with the dashboard patterns and
  trivial to test.
- The optimistic bubble is replaced by the authoritative history render on
  the next poll, so the client never maintains a divergent copy of the thread.
- The trends button and the inline trigger (ticket 16) both flow through
  `researchTrends` + `sendChatMessage`; the page does not re-implement
  detection.

## Testing Decisions

- New `frontend/app/chat.test.tsx` (vitest, mocking `lib/api.ts` — prior art:
  `ab-experiments.test.tsx`, `adaptation-studio.test.tsx`):
  - renders user/mind/system messages from a history fixture;
  - sending a message optimistically renders it, then renders the reply;
  - "your Mind is thinking…" shows while awaiting and disappears after;
  - rule chips render from the `rules` response; trend chips from
    `researchTrends`;
  - error banner renders the backend message on 502;
  - polls history while a reply is pending.
- `frontend/lib/api.test.ts` extended for the three new calls (URL, method,
  body, response mapping).

## Out of Scope

- Streaming (the messaging API is poll-based).
- Editing/deleting chat messages.
- Auto-scroll polish beyond a basic "scroll to bottom on new message".
- Chat history export.

## Further Notes

Commit on `main` as a single conventional `feat(chat): …` commit. Run
`npm run typecheck` and `npm run build` before committing.