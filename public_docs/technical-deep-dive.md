---
public: true
type: technical-deep-dive
title: Technical Deep-Dive — Leaploop
order: 2
summary: A deterministic Python engine and a FastAPI + React cockpit sharing one SQLite DB, behind SSO on a home server.
read_minutes: 4
---

# Leaploop — Technical Deep-Dive
## Stack
Backend engine and API are Python (FastAPI). The cockpit UI is React 18 + Vite with TanStack Query. State is a single SQLite database shared by both halves. Resumes compile from LaTeX via `tectonic` (with a Docker texlive fallback). Deployed as one Docker container on port 8509, fronted by Cloudflare Tunnel → NPM proxy → Authentik forward-auth (single user).

## Architecture
Two halves share one SQLite DB. A **cron watcher** (every 30 min) runs the engine pipeline independently of the web path; the **cockpit** (FastAPI serving the React build + `/api`) imports `engine/` directly rather than reimplementing tailoring/IMAP/LaTeX in JavaScript.

The pipeline: `watcher` polls 12 verified ATS JSON feeds (Greenhouse/Lever/amazon.jobs) and ingests LinkedIn alert-emails over IMAP → `cleaner` applies locked India-PM filters, an experience-ceiling check, dedupe, and drops already-applied roles → `tiering` resolves A/B/C/U → roles land in Triage. On *yes*, `tailor` scores the JD against keyword clusters and `\renewcommand`s flex macros over a master LaTeX template → `pdf` compiles a constant-named PDF surfaced in the Apply queue. `gmail_confirm` matches confirmation emails and flips roles to "applied."

## Key decisions
**1. Deterministic rules, no LLM in the loop (adr-002).** Job matching is keyword-cluster scoring; the UI shows a transparent theme-overlap count, never a black-box rank. Results stay explainable and free, and zero confident match falls back to the safe master resume — never a wrong-but-confident CV.

**2. ATS JSON feeds over scraping.** Sourcing uses public ATS APIs; the account the owner applies from is never used to scrape. Watch-list companies without a public feed (Workday/iCIMS) are covered by a LinkedIn-email backstop instead.

**3. SQLite, not spreadsheets (adr-005).** All state is queryable history in SQLite — `roles`, `applied_index` (dedupe), `feed_health`, `company_tier` — replacing manual xlsx upkeep.

**4. FastAPI imports the engine directly (adr-009).** One language for the proven tailoring/IMAP/LaTeX code; the UI is a thin React port of a bespoke light-only design. Mutations are deterministic; tailoring runs as a background task so the UI stays responsive.
