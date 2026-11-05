---
id: adr-006-leaploop-straight-to-v2
title: Build straight to full v2 (no interim v1 release)
date: 2026-06-03
status: accepted
tags: [scope]
linked_features: [feat-auth-deploy]
---

## Context
An interim v1 would split effort; the engine already works end-to-end on real data.

## Decision
Build straight to the full v2 cockpit + deploy. Task A (verify ATS feeds) ran first to de-risk sourcing. No interim release.

## Consequences
- Single build target; no throwaway v1.
- All 7 pages + deploy are in scope for Stage 3.
- Larger first deployable increment.
