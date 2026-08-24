# 09 — Extract useChatHistory hook

**What to build:** The duplicated `fetchChatHistory` useEffect pattern in `job-clips.tsx` and `adaptation-studio.tsx` is extracted into a shared `useChatHistory()` hook, eliminating copy-paste and ensuring a single source of truth for chat history fetching in components.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Create `frontend/hooks/use-chat-history.ts` exporting a `useChatHistory()` hook that returns `{ messages: ChatMessage[], error: string | null }`
- [x] Hook fetches from `fetchChatHistory()`, handles cleanup with `cancelled` flag, and catches errors
- [x] Replace the inline useEffect in `frontend/components/job-clips.tsx` with `useChatHistory()`
- [x] Replace the inline useEffect in `frontend/components/adaptation-studio.tsx` with `useChatHistory()`
- [x] Add a basic test for the hook (mock `fetchChatHistory`, verify messages state)
- [x] Run lint and typecheck to verify no regressions
