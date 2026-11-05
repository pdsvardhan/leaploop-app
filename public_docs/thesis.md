---
public: true
type: thesis
title: Project Thesis — Leaploop
order: 1
summary: A private, single-user cockpit that turns an India PM job hunt into two fast daily passes — pick and apply.
read_minutes: 3
---

# Leaploop — Project Thesis
## Problem
Tracking India product-manager openings across dozens of company career pages and LinkedIn, then hand-tailoring a resume for each posting, is slow and easy to drop. The work fragments across browser tabs, a spreadsheet, and a LaTeX resume — and the manual upkeep is exactly the part that decays first.

## The bet
Automate everything except judgment. An always-on backend silently sources roles, filters to fit, and tiers companies by reputation; a human only does the two things that actually need a person — deciding *yes/no* on a role, and clicking *apply*. The wager is that a deterministic rules engine (no LLM, no scoring black box) is more trustworthy and cheaper to run than a "smart" ranker, and that protecting the account you apply from (no scraping) matters more than maximal coverage.

## Audience
A single user — its owner, a PM job-hunting in India. This is a personal tool, not a product for others. That constraint is load-bearing: it justifies single-user SSO, no rate limiting, and a self-hosted $0-recurring footprint.

## In scope
ATS-feed + LinkedIn-email sourcing, India-PM filtering and dedupe, A/B/C/unverified company tiering, a two-queue cockpit (Triage, Apply), per-JD rules-based resume tailoring to a constant-named PDF, and Gmail auto-confirmation of "applied."

## Out of scope
Auto-apply (quality and ban risk), LinkedIn scraping, weighted/black-box ranking, any LLM in the recurring loop, dark mode, and analytics/kanban dashboards.

## Success criteria
A new India PM role reaches Triage within ~30 minutes; a "yes" produces a correctly-compiling tailored PDF with zero manual LaTeX; applying plus the confirmation email auto-flips the role to "applied"; and daily use is two quick passes with no other upkeep.
