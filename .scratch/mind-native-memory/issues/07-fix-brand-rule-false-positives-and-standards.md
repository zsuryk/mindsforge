# 07 — Fix brand rule false positives and standards findings

**What to build:** The "Mind remembers" badge no longer shows noisy, irrelevant rules from casual conversation. The preference and acknowledgment regex patterns are tightened to reduce false positives. Additionally, several code standards issues are fixed: dead `debugWarn`/`debugError` exports removed, `MindRemembersBadge` uses the proper union type for `role`, and index-as-key on rule badges is replaced with a stable key.

**Blocked by:** None — can start immediately.

**Status:** done

- [ ] Tighten `PREFERENCE_PATTERNS` in `insights.ts` to require stronger signals (e.g. multi-word patterns or stronger modal verbs like "always"/"never"/"must"/"prefer" without the weak matches on "use"/"keep"/"want"/"need")
- [ ] Tighten `ACKNOWLEDGMENT_PATTERNS` in `insights.ts` to exclude bare "I'll" — require the verb to follow a Mind-role message or be paired with "remember"/"got it"
- [ ] Add tests for `collectConversationBrandRules` that verify "I use this software daily" is NOT flagged as a brand rule
- [ ] Add tests for `collectConversationBrandRules` that verify "I'll go to the store" is NOT flagged as an acknowledgment
- [ ] Remove unused `debugWarn` and `debugError` exports from `frontend/lib/logger.ts`
- [ ] Change `MindRemembersBadge` `Message` type from `role: string` to `role: "user" | "mind" | "system"`
- [ ] Replace `key={index}` with a stable key (e.g. `key={rule.text}` or `key={`${rule.role}-${index}`}`) on rule badges in `MindRemembersBadge`
- [ ] Run lint and typecheck to verify no regressions
