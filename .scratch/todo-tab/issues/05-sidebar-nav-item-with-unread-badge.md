# 05 — Sidebar nav item with unread badge

**What to build:** Add a "Todo" navigation item to the sidebar with a `Bell` icon and an unread count badge that polls the API. This gives users a persistent entry point to the todo feed.

**Blocked by:** 01 (needs the `GET /todos/unread-count` endpoint)

**Status:** ready-for-agent

- [ ] "Todo" nav item added to sidebar between Dashboard and Chat, using `Bell` icon from lucide-react
- [ ] Route set to `/todo`, active state highlighting matches existing nav items
- [ ] Unread badge: red circle with white count, positioned on the nav item
- [ ] Badge fetches from `/todos/unread-count` on mount and polls every 30 seconds
- [ ] Badge hides when count is zero
- [ ] Tests verify: badge renders with correct count, hides at zero, polling updates the count
