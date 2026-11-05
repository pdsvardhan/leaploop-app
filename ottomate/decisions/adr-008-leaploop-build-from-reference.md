---
id: adr-008-leaploop-build-from-reference
title: Cockpit components built bespoke from the reference design (no catalog pick)
date: 2026-06-03
status: accepted
tags: [ui, components]
linked_features: [feat-triage-queue, feat-apply-queue, feat-tracker, feat-settings, feat-manual-generate]
---

## Context
Stage 2.4 expects each page component to be picked from the master_components catalog,
which is currently empty. LeapLoop already has a complete, decided, bespoke design:
app/theme.css (the green "Donezo" token system), app/components.jsx, and seven built
screens (screens-home/triage/apply/settings/misc). Picking generic catalog components
would invent alternatives to a finished design.

## Decision
All 29 Doc 4 components are recorded as skip-with-reason ("built bespoke from the
LeapLoop reference"). Stage 3 builds them directly from the reference code and tokens.
No generic master_components are used; nothing is left unresolved at the 2.4 exit gate.

## Consequences
- Full visual fidelity to the owner's reference; no design drift from catalog substitution.
- These components are NOT added to the cross-project catalog now; the reusable primitives
  (button, card, badge, modal, toast, table, toggle, sidebar) could be seeded later if wanted.
- Stage 2.4 exit gate is satisfied via documented skip_reason (no media-dashboard regression).
