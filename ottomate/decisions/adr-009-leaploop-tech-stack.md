---
id: adr-009-leaploop-tech-stack
title: Cockpit tech stack -- FastAPI + React/Vite on shared SQLite
date: 2026-06-03
status: accepted
tags: [tech, architecture]
linked_features: [feat-auth-deploy, feat-rules-tailor, feat-pdf-compile]
---

## Context
The brief left the cockpit framework "TBD Stage 2". Two facts decide it: the engine is
already substantial, working Python (watcher/cleaner/tiering/rules-tailor/texlive/IMAP/
Telegram), and the UI reference is React (app/*.jsx). The owner delegated the choice.

## Decision
FastAPI (Python) backend + React 18 / Vite frontend on the existing shared SQLite DB.
The backend imports the engine package directly (on-demand tailoring calls engine.tailor +
engine.pdf in-process, no subprocess). The frontend ports the reference JSX 1:1 with the
theme.css token system (hand-CSS, no utility framework). Server state via TanStack Query.
The recurring watcher stays a cron process sharing the DB. Tests: pytest (engine + API),
Vitest + React Testing Library (components), Playwright (the 6 flows).

## Consequences
- One language for all job logic; zero reimplementation of the engine in JS.
- Tailoring is in-process and synchronous (one job at a time) — simplest correct path.
- The reference design ports directly; no design drift.
- The Ottomate tech_stacks table has no write API in this build, so the stack is recorded
  in this ADR + CODING_GUIDELINES.md + the architecture-summary doc rather than that table.
