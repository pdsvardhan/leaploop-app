---
id: adr-004-leaploop-tiering-curated-wikidata
title: Reputability tiering = curated Tier-A/B + keyless Wikidata; OpenCorporates dropped
date: 2026-06-03
status: accepted
tags: [tiering]
linked_features: [feat-tiering]
---

## Context
Roles need a reputability signal to prioritise without a paid data source or black-box ranking.

## Decision
Tier from a curated TIER_A/TIER_B list first, then keyless Wikidata size/notability for B/C, else flag unverified (U). OpenCorporates (paid) is dropped. No weighted-score math.

## Consequences
- $0 reputability signal; transparent and tunable (e.g. Paytm->C).
- Unclassifiable companies surface as 'unverified' with eyeball links rather than being dropped.
- Tier list is hand-maintained in config.py.
