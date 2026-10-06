# 06 — Todo page frontend

**What to build:** The `/todo` page with a card-based feed of todo items, filters, mark-as-read, archive, and empty state. This is the main UI for viewing and managing Mind-initiated notifications.

**Blocked by:** 01 (needs the `GET /todos` and `PATCH /todos/{id}` endpoints), 05 (needs the sidebar nav item so users can navigate here)

**Status:** resolved

- [ ] Page at `/todo` with header showing "Todo" and total item count
- [ ] Filter bar: All, Unread, by type (weekly digest, clip suggestion, experiment result, trend alert)
- [ ] Card feed: scrollable list, each card shows type icon (colored by type), title, body snippet (truncated), relative timestamp, action button (if action_url present)
- [ ] Mark-as-read: triggered when card is viewed for >2 seconds
- [ ] Archive button per card with confirmation dialog
- [ ] Empty state: "No todo items yet — your Mind will notify you here when there's something important."
- [ ] 30-second polling for new items
- [ ] Tests verify: cards render correctly for each type, filters work, mark-as-read decreases unread count, archive removes item from feed, empty state displays when no items
