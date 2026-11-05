---
id: adr-003-leaploop-telegram-only-push
title: Push notifications via Telegram only (Web Push/VAPID cut)
date: 2026-06-03
status: superseded
superseded_by: adr-010-leaploop-telegram-dropped
tags: [notifications]
linked_features: [feat-telegram-push]
---

> **SUPERSEDED by [adr-010](adr-010-leaploop-telegram-dropped.md) (2026-06-04).** The Telegram
> integration described below was built, then **dropped entirely** (token revoked, `engine/notify.py`
> deleted, push removed from the cycle/cockpit/API). LeapLoop has **no push channel**; Tier-A roles
> surface in the Triage queue (badged + sorted first). Treat this ADR as historical.

## Context
Tier-A roles should alert the owner within ~30 min. Web Push/VAPID added browser-permission and service-worker complexity for a single user.

## Decision
Push is Telegram-only via the leap_loop_bot bot. Web Push is cut. Push stays dormant (no error) until TELEGRAM_CHAT_ID is configured.

## Consequences
- Simple, phone-friendly alerts with no browser plumbing.
- Blocked on obtaining the Telegram CHAT_ID (parked).
- Only Tier-A roles push; B/C are pulled in the cockpit.
