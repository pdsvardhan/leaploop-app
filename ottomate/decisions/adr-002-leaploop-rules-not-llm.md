---
id: adr-002-leaploop-rules-not-llm
title: Tailoring is a deterministic rules engine, no LLM in the recurring loop
date: 2026-06-03
status: accepted
tags: [tailoring, architecture]
linked_features: [feat-rules-tailor]
---

## Context
Per-JD resume tailoring needs to be fast, free, and predictable, and must never fabricate content for honest gaps.

## Decision
Tailoring maps JD keywords to flex macros + a P5 variant via a rules table (rules.yaml), writing a per-JD .tex. No LLM or metered API runs in the recurring loop. Low-confidence matches fall back to the safe default master. A metered-API upgrade is optional later, outside the loop.

## Consequences
- Zero recurring API cost; deterministic, reviewable output.
- Quality ceiling is the rules table + flex macros, refined over time.
- Swap-variant lets the user override a pick manually.
