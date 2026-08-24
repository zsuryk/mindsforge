# 05 — Add "Mind remembers" badge to clip/adaptation cards

**What to build:** Clips and adaptations display which brand rules from the creator's conversation influenced the output, demonstrating memory persistence to judges.

**Blocked by:** 01 — Inject conversation thread into generation prompts

**Status:** done

- [x] New `MindRemembersBadge` component parses brand rules from conversation history
- [x] Badge appears on clip cards in the dashboard showing relevant rules
- [x] Badge appears on adaptation cards in the clip studio showing relevant rules
- [x] Rules displayed as chips with the rule text
- [x] Component handles empty state gracefully (no rules yet)
