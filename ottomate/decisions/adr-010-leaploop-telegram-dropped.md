# adr-010 — Telegram push dropped: no notification channel; the Triage queue is the only surface

- **Status:** accepted
- **Date:** 2026-06-04
- **Supersedes:** adr-003 (Notifications via Telegram only — Web Push complexity cut)
- **Tags:** notifications, curated, cat:product

## Context

adr-003 chose Telegram as the single push channel for Tier-A role alerts (Web Push
was cut). The Telegram integration was built (a `leap_loop_bot` bot, an
`engine/notify.py` sender, a cockpit integrations row + sidebar promo, and an
`/api/integrations` telegram block) but stayed dormant pending a `TELEGRAM_CHAT_ID`.

In the 2026-06-04 QA pass (commit `c8566b6`) it was **dropped entirely**: the bot
token was revoked and `engine/notify.py`, the push step in the cron cycle, the
cockpit row/sidebar promo, and the `/api/integrations` telegram block were all
removed. It proved low-value for a single user who already opens the cockpit twice
a day — a push channel added moving parts and a standing secret for no real gain.

## Decision

LeapLoop ships with **no notification/push channel**. New roles (including Tier-A)
surface only in the **Triage queue** in the cockpit, where Tier-A roles are badged
and sorted first. `/api/integrations` reports Gmail only. The `TELEGRAM_BOT_TOKEN`
secret is removed. Re-add a push channel later only if real-time Tier-A alerting
proves worth the moving parts.

This supersedes adr-003. The original success criterion "Tier-A roles fire a
Telegram alert within ~30 min" is replaced by "a new Tier-A role surfaces in the
Triage queue within ~30 min of discovery."

## Consequences

- One fewer external dependency and one fewer standing secret.
- No real-time alerting: the owner relies on the twice-daily Triage pass (acceptable
  by design for a single-user tool).
- Several in-repo planning docs (README, ARCHITECTURE, BUILD_PLAN, LEAPLOOP_BRIEF,
  CODING_GUIDELINES) still referenced Telegram as live; they were reconciled in the
  2026-06-30 Ottomate deep-dive. `public_docs/retrospective.md` already recorded the
  drop; this ADR closes the decision-ledger gap (the drop had never been recorded as
  an ADR).

## Notes

Source: `iteration-log.md` (2026-06-04, commit `c8566b6`),
`public_docs/retrospective.md`, `engine/run.py` (no notify step),
`cockpit/api/service.py` (integration_status → gmail only).
