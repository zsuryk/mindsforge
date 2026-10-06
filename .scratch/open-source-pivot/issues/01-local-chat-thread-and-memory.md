# 01: Local chat thread and memory in SQLite

**What to build:** The chat conversation thread moves from the remote Minds Builder conversation to a local `chat_messages` table (migration included). `fetch_chat_history`, `build_chat_context`, chat initialisation, and `notify_mind`/`post_chat_notification` all read/write SQLite. The Mind's LLM replies still come from the existing Minds call for this ticket — this isolates the storage migration. Chat UI, system chips, and the Memory Inspector's Mind view keep working unchanged.

**Blocked by:** None (can start immediately).

**Status:** done (ed36257)

- [x] Alembic migration creates `chat_messages` (role, text, created_at, thread id) and a migration test follows `test_migrations.py` prior art
- [x] `fetch_chat_history` returns role-annotated messages from SQLite with the same `ChatMessage` schema
- [x] `build_chat_context` renders from SQLite with the 4000-char cap and excludes the init instruction
- [x] Init instruction is inserted once when the thread is empty; notifications insert system rows with the `[MindsForge] ` marker
- [x] Chat send flow still produces Mind replies and persists creator message, notification, and reply rows
- [x] Chat, dashboard, memory API tests pass unchanged
