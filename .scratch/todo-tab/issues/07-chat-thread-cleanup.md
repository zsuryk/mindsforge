# 07 — Chat thread cleanup

**What to build:** Remove system messages from the chat UI for new events now that they are surfaced via the todo tab. Existing system messages in chat history remain (no migration). The chat becomes a clean human↔Mind conversation.

**Blocked by:** 02 (weekly digest no longer posts to chat), 03 (experiment/adaptation results are in todo items)

**Status:** resolved

- [x] Verify that no new system messages are posted to chat for weekly digests, experiment conclusions, or adaptation completions
- [x] Existing system messages in chat history remain visible (no migration, no removal)
- [x] The `SYSTEM_MARKER` prefix and system message rendering logic remain in the codebase for backward compatibility with historical messages
- [x] The `notify_mind()` function remains available but is no longer called by experiment conclusion, adaptation completion, or weekly digest flows
- [x] Tests verify: after all callers are migrated, no new system messages appear in chat history for these events; historical system messages still render correctly
