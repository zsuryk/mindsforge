# 18 — Mind notifications into the chat thread

**What to build:** Tell the Mind about outcomes it did not witness. When an
Experiment concludes (or fails) and when an Adaptation is generated, post a
system-marked message into the `mindsforge-chat` conversation so the Mind
learns the outcome from its own thread and remembers it natively — closing
the gap where the chat Mind otherwise could not answer "what did my
experiments teach me?".

**Blocked by:** 15 (uses `CHAT_ALIAS` and the `SYSTEM_MARKER` convention)

**Status:** ready-for-agent

## Problem Statement

The chat Mind only knows what is in its conversation. Experiment conclusions
and adaptation generations happen in other conversations and background
worker passes, so the chat Mind is blind to them. Without a bridge, the
persistence demo stops at rules and trends — experiments and adaptations, the
core of the product, stay invisible to the Mind it is supposed to be.

## Solution

- `minds.notify_mind(text) -> None`: posts
  `{alias: CHAT_ALIAS, messageText: f"{SYSTEM_MARKER}{text}"}`. Best-effort:
  any MindsError is logged and never propagates to the caller — a
  notification must not fail an Experiment or Adaptation that already
  succeeded.
- Call sites:
  - `ab_testing._conclude_experiment` success → "Experiment concluded on clip
    '<clip title>' (<platform>). Winner: <variant id>. Learned insight:
    '<reasoning>'."
  - `ab_testing._fail_experiment` → "Experiment <id> failed: <error message>."
  - `adaptations.generate_adaptation` READY → "Adaptation ready: '<clip
    title>' for <platform>/<surface> — <brief feature summary>."
- Not notified (documented decisions): brand-rule saves (the statement is
  already in the thread — a duplicate would spam the Mind); trend research
  (the research message IS the notification, ticket 16).
- UI contract (consumed by ticket 19): system messages render as small system
  chips with the marker stripped; the Mind's acknowledgment replies render as
  normal Mind messages — a visible acknowledgment is a feature for the demo
  ("the Mind confirmed it learned"). If acknowledgments prove noisy, a
  follow-up may suppress them in the UI only (history keeps them).

## User Stories

1. As a creator, I want my Mind to know the outcomes of my experiments and
   adaptations, so I can ask it anything about my work and it answers from
   its own memory.
2. As a creator, I want the chat thread to show what my Mind was told, so I
   trust the background work is actually reaching it.
3. As an operator, I want notification failures to never break the underlying
   operation, so an offline Minds API cannot take down a concluded Experiment
   or a READY Adaptation.

## Implementation Decisions

- Notifications use the existing message POST path (`_ensure_conversation` +
  POST message, no reply waiting) — fire-and-forget by design.
- A notification may arrive while a user message awaits a reply; the
  attribution edge case is already documented and accepted in ticket 15 (the
  UI polls the full history, so the true reply always surfaces).
- Notification text uses the glossary vocabulary (Experiment, Learned
  insight, Adaptation) so the Mind's answers stay in-domain.

## Testing Decisions

- `backend/tests/test_ab_testing.py`: a concluded Experiment posts a
  notification with the winner and insight; a failed Experiment posts one
  with the error; a Minds failure during the notification does not change the
  Experiment's CONCLUDED/FAILED state (the notification is swallowed and
  logged).
- `backend/tests/test_adaptations.py`: a READY Adaptation posts the marked
  message; a notification failure leaves the Adaptation READY.
- `backend/tests/test_minds.py`: `notify_mind` sends to `mindsforge-chat` with
  the marker prefix; unconfigured Minds logs and returns without raising.
- Frontend: chat-page tests (ticket 19) render a system chip from a marked
  history row.

## Out of Scope

- Notifying about job scoring (the chat would drown; scoring is per-clip and
  per-job, while Experiment/Adaptation outcomes are discrete events).
- A notification history table — the thread itself is the record.
- Suppressing Mind acknowledgment replies (documented as a possible follow-up).

## Further Notes

Commit on `main` as a single conventional `feat(chat): …` commit.