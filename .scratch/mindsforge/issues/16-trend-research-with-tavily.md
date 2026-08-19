# 16 — Trend research with Tavily

**What to build:** App-side trend research for the chat. A Tavily-backed
service that searches the web from the chat ("Research trends" button or a
"search trends for X" message trigger), saves the results to the Mind's
`trend_research` memory key, posts them into the chat thread so the Mind
answers grounded in live data, and feeds the latest research into adaptation
generation so hooks/tags/captions follow current trends.

**Blocked by:** 15 (uses `POST /chat/messages`, the `SYSTEM_MARKER`
convention, and the chat thread)

**Status:** ready-for-agent

## Problem Statement

The Mind's packaging prompts have no sense of what is trending. The creator
has a Tavily API key and the Mind platform has its own Tavily app connection,
but app-side search is the only deterministic path that lands structured
results in memory (the Mind's freeform replies cannot be parsed into
`trend_research`). Trend data must flow into both the chat (grounded answers)
and adaptation generation (better hooks/tags/captions).

## Solution

- `TAVILY_API_KEY` added to `Settings` (default `""`).
- New `app/services/trends.py`:
  - `TrendResult{title, url, content}` and
    `search_trends(query, max_results=5) -> list[TrendResult]` via
    `POST https://api.tavily.com/search` with `{api_key, query, max_results,
    search_depth: "basic"}`.
  - `TrendSearchError` when `TAVILY_API_KEY` is unconfigured (message names the
    key) or the request/parse fails.
- `POST /chat/trends {query, platform?}` → `200 {results: [...]}`:
  1. run the search;
  2. append to the `trend_research` memory key: list of
     `{query, platform?, results: [{title, url, content}], researched_at}`,
     keep the last 10 entries;
  3. post a system-marked notification to the chat thread —
     `"Researched '<query>': 1. <title> — <url> …"` (top 3 results in the
     message; the Mind reads it and can answer grounded in it);
  4. return the results for the UI chip.
  Unconfigured Tavily → `502` with the clear message.
- Inline trigger: `POST /chat/messages` detects
  `/search (?:for|trends? in|trends? for) (.+)/i` in the message and runs the
  same search-and-notify before posting the user message (single round trip).
  Unconfigured Tavily → `502` with the clear message (explicit intent must not
  silently degrade).
- Generation injection (adaptations only — scoring stays untouched):
  `adaptations._memory_context` appends a trend block to the memory context
  built from `trend_research`: the latest 5 entries within 7 days, each result
  `content` truncated to ~200 chars. No trend data → no block → zero behaviour
  change for existing flows.
- `MEMORY_CONTEXT_KEYS` in `minds.py` gains `"trend_research"` so every prompt
  that already carries memory context also sees the bounded trend research.

## User Stories

1. As a creator, I want to ask my Mind to research a topic and get answers
   grounded in live search results, so my content decisions follow what's
   trending now.
2. As a creator, I want the trends my Mind researched to shape the hooks,
   tags, and captions in my adaptations, so packaging stays current.
3. As an operator, I want a missing Tavily key to fail loudly with a clear
   message, so I never silently ship trend-blind content.

## Implementation Decisions

- Search results are posted into the chat as a system-marked message (not
  appended to the user's message text), so the thread stays readable and the
  Mind sees the data as an event it remembers.
- Injection targets adaptations only (grilled decision): clip scoring keeps its
  honest-read design and the job pipeline stays isolated from trend drift.
- `trend_research` and `brand_rules` (ticket 17) are bounded lists; the
  `MEMORY_CONTEXT_VALUE_LIMIT` truncation in `build_memory_context` remains the
  final safety net.
- Open-ended trend questions without the explicit trigger are handled by the
  Mind itself via its own Tavily connection (instructed at chat
  initialisation, ticket 15) — best-effort, not a dependency.

## Testing Decisions

- New `backend/tests/test_trends.py`:
  - `search_trends` happy path with a stubbed Tavily HTTP call; unconfigured
    key → `TrendSearchError` naming `TAVILY_API_KEY`.
  - `POST /chat/trends` persists to `trend_research` (bounded to 10), posts
    the marked chat message, returns results.
  - inline trigger: "search trends for fitness shorts" runs the search and
    posts the notification before the user message; a message without the
    trigger sends untouched.
  - unconfigured Tavily → 502.
- `backend/tests/test_adaptations.py` or `test_minds.py`: the adaptation read
  prompt carries the trend block when `trend_research` exists and is absent
  when it is empty (existing prompts/tests stay green).
- Frontend: the chat page tests (ticket 19) cover the trends button and chip.

## Out of Scope

- Invoking the Mind's trend-hunter skill or platform Tavily connection
  programmatically — best-effort prompt instruction only.
- Seeding clip-scoring prompts with trends (adaptations only, per decision).
- Scheduled/background trend polling (search happens on demand from the chat).

## Further Notes

Commit on `main` as a single conventional `feat(chat): …` commit.