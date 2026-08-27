# 01 — TodoItem data model, service, and API

**What to build:** A new `TodoItem` database table, a `TodoService` class for creating and querying items, and four API endpoints so the backend can create todo items and the frontend can list, filter, mark read, and archive them. This is the foundation for all other todo tab tickets.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] `TodoItem` model with fields: `id` (UUID4), `type` (enum: `weekly_digest`, `clip_suggestion`, `experiment_result`, `trend_alert`), `title` (String 255), `body` (Text), `action_url` (String 512 nullable), `action_label` (String 64 nullable), `is_read` (Boolean, default false), `is_archived` (Boolean, default false), `created_at` (DateTime)
- [x] Alembic migration for the `todo_items` table
- [x] `TodoService` class with methods: `create_todo`, `list_todos` (filterable by type, unread, archived), `mark_read`, `archive`, `unread_count`
- [x] `GET /todos` — returns `{items: [...], unread_count: N}`, query params: `type`, `unread`, `archived` (default false)
- [x] `PATCH /todos/{id}` — accepts `{is_read?, is_archived?}`, returns updated item
- [x] `GET /todos/unread-count` — returns `{count: N}`
- [x] `POST /todos` — accepts `{type, title, body, action_url?, action_label?}`, returns created item
- [x] Unit tests for `TodoService`: create, list with each filter combination, mark_read, archive, unread_count
- [x] Integration tests for all four API endpoints
