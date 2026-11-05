---
id: adr-001-leaploop-initial-staging
title: Initial Stage 1 staging for LeapLoop
date: 2026-06-03
status: accepted
tags: [staging, initial]
linked_features: [feat-ats-watcher, feat-cleaner, feat-rules-tailor, feat-pdf-compile, feat-triage-queue, feat-apply-queue, feat-auth-deploy]
---

## Context
LeapLoop is a private, single-user, self-hosted PM job-hunt cockpit for Sai Vardhan Palli. The backend engine (watcher/cleaner/tiering/rules-tailor/texlive/gmail-confirm/telegram) is built and CLI-verified end-to-end on real data (1032 roles -> 70 clean India-PM; 31 KB tailored PDF). The cockpit UI and deploy are not yet built. This ADR locks the Stage 1 spec foundation.

## Decision
Scope locked at 14 features / 6 flows / 7 cockpit pages, target both devices, hosting vault7a-docker on port 8509 at leaploop.vault7a.xyz behind Authentik SSO. Source of truth for sourcing is ATS JSON feeds + LinkedIn alert emails (no scraping). Human footprint = pick + apply only.

## Consequences
- Stage 2 inherits: UI master plan from the green Plus-Jakarta 'Donezo' reference (light-only), component picks, tech/architecture/build-plan.
- Locked-for-iteration: no auto-apply, no scraping, no LLM in the recurring loop, no weighted-score ranking.
- Deferred: prior-applications import, Telegram CHAT_ID, P5-D/P5-G cluster confirmations. <!-- 2026-06-30: the import was done (41 Status='Applied' rows, not 74); Telegram was later dropped (adr-010). -->
- Tech hints carried for Stage 2 BUILD: Python engine + SQLite already exist; cockpit framework TBD in Stage 2.
