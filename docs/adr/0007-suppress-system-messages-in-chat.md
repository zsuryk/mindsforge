# Suppress system messages in chat thread

System notifications (experiment conclusions, adaptation ready, trend research) are posted into the chat conversation so the Mind learns of outcomes natively. The UI renders these as `role: "system"` centered chips, but they clutter the human↔Mind conversation — especially when multiple experiments and adaptations run concurrently. The dashboard's "Mind at Work" activity panel already surfaces the same events in a structured, icon-rich format, making the inline chat messages redundant for the user.

We filter system messages out of the chat thread on the frontend (both Chat page and Memory Inspector "Mind's View"), defaulting to hidden. A toggle lets the user opt in to seeing them; the toggle state persists in `localStorage`. A badge count on the toggle signals that background events occurred without requiring the user to open the feed. The Mind still receives every notification — only the user's view is filtered.

Separately, `mind-notified` events are removed from the dashboard activity log. Every `mind-notified` is triggered by a more specific parent event (`experiment-concluded`, `adaptation-ready`, etc.) that already appears in the feed, so the meta-event is redundant noise.

**Considered Options:**
- Backend filtering via `?exclude_system=true` query param on `/chat/history` — cleaner API contract, but the Memory Inspector (a debugging tool) loses the ability to see system messages entirely.
- Always hide with no toggle — simpler, but removes the user's ability to inspect what the Mind was told during debugging or curiosity.

**Consequences:**
- The chat thread becomes a clean human↔Mind conversation by default.
- The Memory Inspector retains full visibility via the toggle, preserving its debugging value.
- The dashboard "Mind at Work" panel is the single source of "what is Minds doing right now."
- `notify_mind()` continues posting to the Minds API unchanged — the Mind's own thread context is unaffected.
- `mind-notified` icon mapping stays in code for backward compatibility with existing activity rows, but no new rows are created.
