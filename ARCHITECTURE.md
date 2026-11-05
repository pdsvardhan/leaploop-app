# LeapLoop — Architecture (shipped)

Single-user, self-hosted PM job-hunt cockpit on VAULT7A. Two halves that share one SQLite DB:
a **deterministic Python engine** (runs on cron) and a **cockpit** (React/Vite UI + FastAPI backend). Both are built and live (shipped Stage 3).

## Topology
- Public entry: `https://leaploop.vault7a.xyz` → **Cloudflare Tunnel** → **NPM proxy** → **Authentik forward-auth** (single user) → cockpit container on port **8509**.
- Cockpit container = FastAPI serving the React static build + `/api`. Imports `engine/` directly.
- **Watcher cron** (every 30 min, `run_cycle.sh`) runs the engine pipeline and writes to the shared SQLite DB. Independent of the web request path.
- **texlive/tectonic** compiles the per-JD `.tex` → constant-named PDF, stored on a volume the cockpit serves (protected).
- See `architecture/topology.mmd`.

## Components
- `engine/` — `watcher` (ATS feeds), `feeds` (verified ATS endpoints), `cleaner` (India-PM filter + dedupe + drop-applied), `tiering` (curated + Wikidata), `tailor` (rules.yaml → flex/P5 → per-JD `.tex`), `pdf` (tectonic), `gmail_confirm` (IMAP), `run` (cycle orchestrator). (No `notify` module — Telegram push was dropped, adr-010.)
- `cockpit/api` (FastAPI) — roles list/triage, on-demand tailoring (calls `engine.tailor`+`engine.pdf`), apply/applied state, manual generate, settings/filters, watcher health, PDF serving.
- `cockpit/web` (React/Vite) — 7 screens: login, home/inbox, triage, apply, tracker, generate, settings (ports `Downloads/LeapLoop/app`).

## Data flow
1. **Source→Triage** (cron): watcher → cleaner → tiering → write `roles(state='triage')`; Tier-A roles are badged and sorted first in the Triage queue (no push channel — Telegram was dropped, adr-010). See `architecture/dataflow.mmd`.
2. **Triage** (user): Yes → `state='picked'` + enqueue tailoring; No → `skipped`; Snooze → resurfaces; Mute → company filtered next cycle.
3. **Tailor→Apply** (backend): JD keywords → flex/P5 → `.tex` → tectonic → constant-named PDF → `roles.pdf_path`, surfaced in Apply.
4. **Apply→Confirmed**: user applies on the ATS; `gmail_confirm` matches the confirmation email → `applied=1`, `applied_at`, recorded resume; manual override available.

## Data model (existing SQLite — `data/leaploop.db`)
- `roles` (source_id PK; company/title/location/mode/source/url/jd_text/tier/fit_hint/gaps/state/variant/pdf_path/applied/applied_at/first_seen)
- `applied_index` (company_norm+title_norm PK) — dedupe; one-time import of the 41 prior applications (the source tracker xlsx had 74 rows; 41 were Status='Applied')
- `feed_health` (company PK; ok/count/err/last)
- `company_tier` (name PK; tier/decided_at/via)

## Cross-cutting
- **Auth:** Authentik SSO (forward-auth at proxy); app trusts upstream-authenticated identity. No anonymous pages except the SSO splash.
- **Secrets:** `/opt/homeserver/leaploop/secrets.env` (off-git). Names only in the tracker.
- **Failure posture:** per-feed `alert-and-skip`; LinkedIn-email backstop for feed gaps; low-confidence tailoring → safe master.
- **Observability gap (open risk `no-error-tracking`):** wire GlitchTip in Stage 3.

## Known tracker gap
`tech_stacks` has a table but no write API in this Ottomate build; the stack is recorded here, in `CODING_GUIDELINES.md`, and in `adr-009-leaploop-tech-stack` instead.
