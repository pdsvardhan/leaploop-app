---
id: adr-005-leaploop-sqlite-not-xlsx
title: DB-backed state in SQLite; no xlsx maintenance going forward
date: 2026-06-03
status: accepted
tags: [data]
linked_features: [feat-tracker, feat-cleaner]
---

## Context
The prior workflow tracked applications in an xlsx by hand, which is error-prone and not queryable by the engine.

## Decision
All state lives in an in-project SQLite DB (roles, applied_index, feed_health, company_tier). The previously-applied rows are imported once into applied_index for dedupe (41 Status='Applied' rows from a 74-row tracker xlsx). No xlsx is maintained going forward.

## Consequences
- Engine + cockpit share one queryable store; dedupe is automatic.
- One-time import job needed for the prior-applied rows (imported: 41).
- No kanban/funnel/analytics in v1.
