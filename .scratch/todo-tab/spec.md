Status: ready-for-agent

# Todo Tab — Mind-Initiated Notifications

## Problem Statement

The Mind generates proactive outputs — weekly trend digests, experiment conclusions, clip suggestions — that currently post as system messages in the chat thread. These get buried in conversation, have no structured feed, and are easy to miss. Users need a dedicated place to see what the Mind is recommending and what has happened in the background. The chat thread is for human↔Mind conversation, not a notification inbox.

## Solution

Add a "Todo" tab to the sidebar — a card-based notification feed of Mind-initiated items. Todo items replace system messages in the chat thread. The backend automatically creates todo items when events happen (experiment concludes, weekly trends run, clips are scored). Each item is actionable (view clip, run experiment, dismiss) and persists until manually archived. A badge on the sidebar nav item shows the unread count.

## User Stories

1. As a creator, I want a dedicated Todo tab in the sidebar, so I can see all Mind-initiated notifications in one place.
2. As a creator, I want the Todo tab to show a badge with the number of unread items, so I know when there's something new without opening it.
3. As a creator, I want weekly digest todo items that summarize top trends, clip performance, and suggestions, so I stay informed about my content strategy.
4. As a creator, I want experiment result todo items that tell me which variant won and what was learned, so I don't have to dig through the A/B experiments page.
5. As a creator, I want clip suggestion todo items that recommend actions based on clip stats (e.g., "Clip X has high virality — consider A/B testing thumbnails"), so the Mind proactively helps me improve.
6. As a creator, I want trend alert todo items when new trends are detected, so I can act on timely opportunities.
7. As a creator, I want each todo item to have a contextual action button (e.g., "View clip", "Run now"), so I can act on suggestions immediately.
8. As a creator, I want to mark todo items as read by viewing them, so the unread count decreases.
9. As a creator, I want to archive todo items I've dealt with, so my feed stays clean.
10. As a creator, I want to filter todo items by type (digest, suggestion, result, alert), so I can focus on what matters most right now.
11. As a creator, I want todo items to persist until I archive them, so I can revisit important digests or suggestions later.
12. As a creator, I want the chat thread to remain a clean human↔Mind conversation without system message clutter, so I can focus on talking to my Mind.
13. As a creator, I want the Mind to still learn about experiment conclusions and adaptation results (via internal notifications), so its memory stays accurate even though chat messages are removed.
14. As a creator, I want the todo tab to show items in reverse chronological order with timestamps, so I can see what happened most recently.
15. As a creator, I want the todo feed to be empty and helpful when there are no items, so I'm not confused by a blank page.

## Implementation Decisions

### Data Model

New `TodoItem` table:

- `id` — UUID4 primary key
- `type` — enum: `weekly_digest`, `clip_suggestion`, `experiment_result`, `trend_alert`
- `title` — String(255), short summary of the item
- `body` — Text, detailed content (may contain markdown)
- `action_url` — String(512) nullable, deep link for the action button (e.g., `/clips/abc123`)
- `action_label` — String(64) nullable, button text (e.g., "View clip")
- `is_read` — Boolean, default false
- `is_archived` — Boolean, default false
- `created_at` — DateTime, auto-set

### API Endpoints

- `GET /todos` — List items, query params: `type` (filter), `unread` (boolean), `archived` (boolean, default false). Returns `{items: [...], unread_count: N}`.
- `PATCH /todos/{id}` — Update fields: `is_read`, `is_archived`. Returns the updated item.
- `GET /todos/unread-count` — Returns `{count: N}`. Used by sidebar badge.
- `POST /todos` — Internal creation endpoint. Not user-facing. Accepts `{type, title, body, action_url?, action_label?}`.

### Service Layer

New `TodoService` class:

- `create_todo(type, title, body, action_url=None, action_label=None)` — Creates and persists a TodoItem. Called by other services.
- `list_todos(type=None, unread=None, archived=False)` — Query with filters.
- `mark_read(id)` — Sets `is_read=True`.
- `archive(id)` — Sets `is_archived=True`.
- `unread_count()` — Count of non-archived unread items.

### Refactoring `notify_mind()`

Split `minds.notify_mind(text)` into two functions:

- `notify_mind(text)` — Keeps posting to the Mind's chat thread (for Mind context/memory). Unchanged behavior.
- `create_todo_item(type, title, body, ...)` — Creates a TodoItem record. New function.

Update callers:
- `ab_testing._conclude_experiment` — Create `experiment_result` TodoItem instead of posting system message to chat.
- `ab_testing._fail_experiment` — Create `experiment_result` TodoItem with error.
- `adaptations.generate_adaptation` — Create `experiment_result` or appropriate type TodoItem.
- `trends._weekly_trends_loop` — Create `weekly_digest` TodoItem with rich content.

The `notify_mind()` call is removed from these callers — they use `create_todo_item()` instead. The Mind no longer receives these as chat messages, but the data is still available via the TodoItem API if the Mind needs it in the future.

### Weekly Digest Generation

The weekly trends loop is enriched to produce a `weekly_digest` TodoItem containing:

- Top 3 trending topics from the week's research
- Clip performance summary (total clips, average virality, top performer)
- 1-2 actionable suggestions based on stats

The digest is generated by querying existing data (clips, experiments, trends memory) and formatting it into a structured body.

### Clip Suggestion Engine

After clips are scored, analyze stats and generate `clip_suggestion` TodoItems:

- High virality score (≥80) → suggest A/B testing thumbnails
- Low virality score (≤30) → suggest reviewing hooks or re-cutting
- Multiple clips from same job → suggest cross-platform adaptation

This runs as part of the scoring pipeline, creating suggestions when conditions are met.

### Frontend — Sidebar

Add "Todo" nav item to sidebar between Dashboard and Chat:

- Icon: `Bell` from lucide-react
- Route: `/todo`
- Unread badge: fetch from `/todos/unread-count`, poll every 30 seconds
- Badge style: red circle with white count, matches existing sidebar aesthetic

### Frontend — Todo Page

New page at `/todo`:

- Header: "Todo" with item count
- Filter bar: All, Unread, by type (dropdown or tabs)
- Card feed: scrollable list of todo cards
- Each card: type icon (colored by type), title, body snippet (truncated), timestamp (relative), action button
- Mark-as-read: triggered when card is expanded or viewed for >2 seconds
- Archive button: per-card, with confirmation
- Empty state: "No todo items yet — your Mind will notify you here when there's something important."
- Polling: refresh every 30 seconds for new items

### Chat Thread Cleanup

- Remove `notify_mind()` calls from experiment conclusions, adaptation completions, and trend research
- Existing system messages in chat history remain (no migration)
- Chat becomes pure human↔Mind conversation
- The `SYSTEM_MARKER` prefix and system message rendering in chat remain for backward compatibility with existing history, but no new system messages are created

### Database Migration

New Alembic migration for the `todo_items` table. No changes to existing tables.

## Testing Decisions

- **Backend unit tests** for `TodoService`: create, list, filter, mark_read, archive, unread_count. Test each method in isolation.
- **API integration tests** for `/todos` endpoints: CRUD operations, filter combinations, badge count.
- **Caller tests**: verify that experiment conclusion, adaptation ready, and weekly digest each create a TodoItem (not a chat message). Verify the correct type, title, and action_url.
- **Weekly digest tests**: verify the digest contains expected sections (trends, stats, suggestions) when data exists.
- **Clip suggestion tests**: verify suggestions are created for high/low virality clips, not for mid-range.
- **Frontend component tests**: todo card renders correctly for each type, badge shows correct count, filter works, archive removes item from feed.
- Prior art: existing tests in `backend/tests/test_ab_testing.py`, `backend/tests/test_adaptations.py`, `backend/tests/test_minds.py` cover similar service-level testing patterns. Frontend tests follow existing page test patterns.

## Out of Scope

- Mind-driven todo creation (the Mind does not directly create todo items via API)
- Auto-expiry of todo items (items persist until archived)
- Push notifications / browser notifications (the badge is the notification mechanism)
- Todo items for job processing status (jobs have their own status page)
- Todo items for user-initiated actions (only Mind-initiated/background events)
- Kanban board or complex task management (this is a notification feed, not a project tracker)
- Real-time WebSocket updates (polling is sufficient for this use case)
- Migration of existing chat system messages to TodoItems

## Further Notes

The todo tab fills a real gap: currently the Mind's proactive outputs have no structured home outside the chat thread. This feature makes the Mind's background work visible and actionable without cluttering the conversation. The backend-driven approach keeps the creation logic close to the events that generate items, avoiding the need for the Mind to know about the Todo API.

Commit on `main` as a single conventional `feat(todo): …` commit, or split into backend + frontend if the changeset is large.
