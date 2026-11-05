---
public: true
type: retrospective
title: Retrospective — Leaploop
order: 4
summary: What got cut, what got simpler, and the tradeoffs behind a deliberately small single-user tool.
read_minutes: 3
---

# Leaploop — Retrospective
## What I cut, and why
**Telegram push shipped, then was removed.** Tier-A roles were meant to fire a Telegram alert; it was built, then dropped entirely (token revoked, `engine/notify.py` deleted) once it proved low-value against the friction of maintaining a bot and chat ID. The pipeline was unchanged by its removal — a sign the notification was a bolt-on, not load-bearing. Lesson: the daily-pass workflow already surfaced new roles; a push channel didn't earn its keep. (Note: some in-repo docs still mention Telegram and are stale relative to the live system.)

**Paid APIs and OpenCorporates dropped** in favor of a curated company list plus keyless Wikidata for tiering (adr-004). Free, good-enough reputability signals beat a paid integration for a personal tool.

## Tradeoffs I'd defend
**Determinism over "smart."** Refusing an LLM in the recurring loop (adr-002) keeps matching explainable and free, and guarantees the resume never goes confidently wrong — a low-confidence JD falls back to the safe master. The cost is shallower matching than a model could do; for a tool whose output is a real job application, predictable-and-correct won.

**Single-user scope as a feature, not a limitation.** No rate limiting and trusting upstream SSO identity are acceptable precisely because there is exactly one user behind Authentik. Designing for one person kept the surface small and the cost at $0 recurring.

## What's honestly unfinished
Cross-component flows aren't tested end-to-end (the engine units are). Error tracking is a dormant hook awaiting a GlitchTip server. Two resume sub-variants (P5-D/P5-G) still fall back to confirmed bullets pending content confirmation — a deliberate refusal to fabricate resume claims for honest gaps. ATS/LinkedIn format drift remains the most likely thing to break a cycle; the mitigation is fail-soft (alert-and-skip) rather than guaranteed coverage.
