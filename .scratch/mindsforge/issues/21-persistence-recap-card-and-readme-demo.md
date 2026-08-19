# 21 — Persistence recap card and README persistence demo

**What to build:** Make cross-session persistence visible at a glance and
provable in a timed demo. A "What your Mind remembers" card on the dashboard
rendering the memory tree (brand voice, recent brand rules, learned insights,
recent trend research), plus a scripted day-1 → day-2 persistence walkthrough
in the README.

**Blocked by:** none (renders whatever memory exists; richer once tickets
16/17 land)

**Status:** ready-for-agent

## Problem Statement

The Mind's memory is real but buried in the Memory Inspector's JSON tree. A
judge must be told the product persists — the rubric rewards *demonstrated*
persistence, and nothing on the landing page proves it. The README also
presents no cross-session story to follow.

## Solution

- Dashboard card "What your Mind remembers" (below the "Mind at Work" panel):
  - fetches `/agent/memory` (existing endpoint, `fetchAgentMemory` in
    `frontend/lib/api.ts`);
  - renders, each with an age ("3 days ago"):
    - brand voice excerpt (first ~120 chars, else an empty-state line),
    - latest 3 `brand_rules` entries (ticket 17),
    - latest 3 learned insights (reuse `collectInsights` in
      `frontend/lib/insights.ts`),
    - latest 2 `trend_research` queries (ticket 16);
  - a "See full memory" link to `/memory-inspector`.
- README changes:
  - new **Persistence demo** section — a scripted ≤5-minute walkthrough:
    Day 1: state a brand rule in chat (chip confirms), research a trend, run
    a clip through adaptation, launch an experiment; Day 2 (restart the
    backend — SQLite and the Minds thread persist): ask the chat "what's my
    brand voice?" and "what did my experiments teach me?" (answers from
    native thread memory via tickets 15/18), generate a new adaptation and
    see the rule applied, watch the Memory Inspector show the accumulated
    history;
  - update the feature bullets (chat with the Mind, trend research, Mind at
    Work feed) and the "What it generates" intro;
  - troubleshooting rows: `TAVILY_API_KEY is not configured`, chat reply
    timeout.

## User Stories

1. As a judge, I want the landing page to show, at a glance, that the Mind
   remembers, so persistence needs no explanation.
2. As a demo runner, I want a scripted two-session walkthrough, so the
   persistence story is provable in five minutes under time pressure.

## Implementation Decisions

- The card consumes the existing memory endpoint and `collectInsights` — no
  new backend surface; empty memory renders honest empty states.
- Timestamps come from the memory values themselves (`created_at` /
  `concluded_at` fields written by tickets 16/17 and the existing experiment
  flow); entries without timestamps render without an age.
- The README demo script mirrors the actual ticket behaviour — it must not
  promise anything the build does not do (per ticket-14 conventions).

## Testing Decisions

- New `frontend/app/persistence-card.test.tsx` (or extend
  `dashboard.test.tsx`): renders brand voice, rules, insights, and trend
  queries from a memory fixture; empty states render; the link points at
  `/memory-inspector`.
- README changes are reviewed against the final behaviour of tickets 15-20
  before commit.

## Out of Scope

- A new backend summary endpoint (the raw memory tree is already fetchable).
- Persistence claims beyond what the product does (e.g. no cross-user memory).

## Further Notes

Commit on `main` as a single conventional `feat(dashboard): …` commit
(README included).