---
id: adr-007-leaploop-light-only
title: Light-only theme (dark mode deferred)
date: 2026-06-03
status: accepted
tags: [ui, theme]
linked_features: [feat-triage-queue, feat-apply-queue]
---

## Context
The Ottomate Stage 2.2 process mandates both a dark and a light palette. LeapLoop's
brief and its design reference (app/theme.css, the green "Donezo" system) are explicitly
light-only; dark mode is on the project's AVOID list. The design is finished and decided.

## Decision
Ship light-only. Store palette_light from theme.css; leave palette_dark null. The
Stage 2.2 "both palettes" rule is intentionally deviated from, recorded here per the
anti-gaslight no-silent-drop rule. A dark palette can be derived mechanically later if
the owner ever wants it (would require a new ui_master_plans version + ADR).

## Consequences
- Single palette to build and maintain; matches the owner's stated preference.
- No dark-mode toggle in the cockpit; theme.css is the single source of visual truth.
- Deviation from the skill's dual-palette gate is explicit and auditable, not silent.
