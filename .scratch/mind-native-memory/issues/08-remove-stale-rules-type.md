# 08 — Remove stale rules type from ChatSendResult

**What to build:** The frontend `ChatSendResult` type in `api.ts` no longer declares a `rules` field, matching the backend `ChatSendOut` schema after ticket 02 removed the rules sidecar.

**Blocked by:** 02 — Remove Groq brand-rule extraction sidecar

**Status:** ready-for-agent

- [ ] Remove `rules: string[]` from `ChatSendResult` in `frontend/lib/api.ts`
- [ ] Verify no frontend code references `ChatSendResult.rules` (the chat UI previously rendered a rules confirmation chip)
- [ ] Run typecheck to confirm no regressions
