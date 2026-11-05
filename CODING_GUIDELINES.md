# LeapLoop — Coding Guidelines

Locked at Stage 2 (2026-06-03). Stage 3 builds against these. Tech stack chosen: **FastAPI (Python) backend + React 18 / Vite frontend, shared SQLite**, reusing the existing `engine/` package.

## Non-negotiables (from the brief — anti-gaslight rails)
- **No LLM or metered API in the recurring loop.** Tailoring is deterministic rules only (`engine/rules.yaml`). A metered-API upgrade, if ever, lives outside the loop and behind an explicit flag.
- **No scraping** the account he applies from. Sourcing is ATS JSON feeds + LinkedIn alert emails (Gmail-IMAP) only.
- **Human footprint = pick + apply only.** No auto-apply, ever.
- **Constant PDF filename:** `Sai_Vardhan_Palli_Product_Manager_IIMB_CV.pdf` — never vary it.
- **Never fabricate resume content** for honest gaps; low-confidence JD match falls back to the safe default master.
- **No weighted-score / black-box ranking.** `fit_hint` is a light qualitative cue (gaps a JD triggers), not a rank.
- **Light-only UI** (`adr-007`); bespoke components from the reference (`adr-008`). `theme.css` is the single source of visual truth.

## Stack & boundaries
- **Backend — FastAPI.** Imports the `engine/` package directly (watcher/cleaner/tiering/tailor/pdf/gmail_confirm/notify). No reimplementation of job logic in JS.
- **Frontend — React 18 + Vite.** Ports `Downloads/LeapLoop/app/*.jsx` 1:1. Built to static assets, served by the backend (or NPM) behind Authentik.
- **DB — SQLite** (the existing `data/leaploop.db`; tables `roles`, `applied_index`, `feed_health`, `company_tier`). Access via Python `sqlite3` with parameterized queries only.
- **Recurring watcher** stays a cron process (`run_cycle.sh`, every 30 min). The cockpit shares the DB; it does **not** re-run sourcing on web requests.
- **Tailoring** is triggered on demand (a "Yes" or manual generate) → backend calls `engine.tailor` + `engine.pdf` in-process; one job at a time.

## Python (backend + engine)
- Python 3.11+. Type hints on public functions. `ruff` + `black` (line length 100). `mypy` advisory.
- Pure functions in the engine; side effects (DB, network, filesystem) isolated and injectable for tests.
- DB writes go through a thin `db.py` layer; **never** string-format SQL — bind parameters.
- Secrets only from `/opt/homeserver/leaploop/secrets.env` (chmod 600, off-git): `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `AUTHENTIK_CLIENT_SECRET`. Read via env; never log values. (The `TELEGRAM_*` vars were removed when Telegram push was dropped — adr-010.)
- External calls (ATS feeds, IMAP, Wikidata) wrapped with timeout + `alert-and-skip`; one bad feed never aborts a cycle. Record `feed_health`.

## Frontend (React/Vite)
- Functional components + hooks. Server state via **TanStack Query**; local UI state via `useState`/`useReducer`. No Redux.
- **Styling = hand-authored CSS with `theme.css` tokens.** No Tailwind/CSS-in-JS. Reuse the reference's class system (`.role`, `.atile`, `.health`, `.tbl`, `.qtabs`, `.modal`, `.toast`, …).
- Icons: lucide-react (matches the reference's stroke style).
- Respect `prefers-reduced-motion` (already in `theme.css`). Animation level: **smooth**.
- Accessibility: WCAG AA contrast (the green tokens already pass), keyboard-operable triage actions, focus-visible rings.

## API conventions
- REST under `/api`. JSON in/out. Single-user, but still validate inputs (pydantic models).
- Auth handled by **Authentik forward-auth** at the proxy; the app trusts the upstream-authenticated header. No in-app login form beyond the SSO splash.
- PDFs served from a protected static path; filename always the constant.

## Testing (gate to "done" per feature)
- **pytest** — engine units (cleaner filters, dedupe, tiering, rules selection, fallback) + API routes.
- **Vitest + React Testing Library** — component behavior (triage actions, swap-variant, applied-toggle).
- **Playwright** — the 6 locked flows (discovery→triage, triage-decision, tailor→PDF, apply→confirm, manual-generate, filter-tune).
- A feature is not "done" until its acceptance criteria have a passing test. (Risk `no-tests` resolves only as coverage lands.)

## Git / deploy
- Commit before rebuild. Always pull before, push after. Branch for non-trivial work.
- Docker on VAULT7A port **8509**; NPM proxy + Cloudflare Tunnel to `leaploop.vault7a.xyz`; Authentik SSO in front.
- Backups: snapshot `data/leaploop.db` before migrations/imports (e.g. the one-time prior-applications import — 41 Status='Applied' rows from the 74-row tracker xlsx).
