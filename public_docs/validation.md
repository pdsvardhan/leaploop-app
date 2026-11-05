---
public: true
type: validation
title: What's Built & Proven — Leaploop
order: 3
summary: Shipped and deployed behind SSO; engine core is unit-tested and the SSO gate was verified.
read_minutes: 3
---

# Leaploop — What's Built & Proven
## Shipped and deployed
Leaploop is marked **shipped**. The cockpit runs in Docker on port 8509 behind Authentik SSO at its private subdomain (Cloudflare Tunnel + NPM). The `*/30` cron watcher is live. Thirteen of fourteen tracked features are **done**: ATS watcher, LinkedIn ingest, cleaner/filter/dedupe, tiering, both queues (Triage, Apply), the rules tailoring engine, texlive PDF compile, manual Generate-PDF, the tracker, Gmail auto-confirm, settings/filter-tuning, and auth+deploy.

## Tested
The deterministic engine core has unit tests covering tiering precision (word-aware curated matching, no loose-substring false positives), the India-PM filter, the years-of-experience parser, recruiter detection, LinkedIn HTML parsing, and the applied-state machine. **12/12 pass** (verified on the live repo). A Stage-4 QA pass on an isolated clone recorded 31/31 API tests plus a desktop+mobile Playwright E2E run, and an independent verifier approved the build. The SSO gate was confirmed (anonymous request → Authentik login, no data leak), and the live API was observed tailoring a real PDF (PhonePe → fintech cluster).

## Proven in real use
A one-time import seeded **41 prior applications** into the dedupe index. The build log records real tailoring runs and iterative fixes driven by the owner's own testing (e.g. a per-company Triage cap to stop a single employer flooding the queue).

## Honest gaps
The six tracker **flows** are marked *not-tested* end-to-end (the engine *features* are tested; the cross-component flows are not). Open risks remain: no error tracking wired (a dormant Sentry/GlitchTip hook plus container logs is the current mitigation), no API rate limiting (single-user behind SSO), and no secret-rotation cadence. ATS-feed and LinkedIn-email format drift is a standing parsing risk, mitigated by per-feed alert-and-skip and the LinkedIn backstop.
