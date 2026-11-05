# LeapLoop — Build Plan (Stage 3)

> ⚠️ **HISTORICAL (flagged 2026-06-30).** This was the Stage-3 plan; the project is now **shipped**.
> Two items here are stale: the "Telegram CHAT_ID" push work was built then **dropped** (adr-010, no
> push channel), and the "74-applied import" actually imported **41** rows (Status='Applied' subset).
> Kept as a historical plan; for current state see `public_docs/` + `ARCHITECTURE.md`.

Order of work for Stage 3. The engine is largely built + CLI-verified; the cockpit + deploy are the remaining bulk. Each item ships with tests against its feature's acceptance criteria.

## Status legend
✓ done & verified · ◑ partial · ☐ to build

## Engine (mostly done)
1. ✓ **feeds.py** — 12 ATS endpoints verified (Task A), 1032 live roles.
2. ✓ **watcher.py** — poll + diff into `roles`; `feed_health`.
3. ✓ **cleaner.py** — India-PM filter + dedupe + drop-applied (1032→70, 0 leaks).
4. ◑ **tiering.py** — curated A/B + keyless Wikidata B/C; tune edge cases (e.g. Paytm→C).
5. ✓ **tailor.py** — rules.yaml → flex/P5 → per-JD `.tex`; safe-default fallback.
6. ✓ **pdf.py** — tectonic → constant-named PDF (31 KB verified).
7. ◑ **gmail_confirm.py** — IMAP match works (49 matched); **wire into the applied-marking loop**.
8. ✗ **notify.py** — Telegram push was coded, then **dropped** (adr-010): `notify.py` deleted, no push channel. New roles surface only in the Triage queue.
9. ◑ **linkedin ingest** — coded; not yet verified end-to-end.

## Cockpit — backend (FastAPI) ☐
10. ☐ Scaffold FastAPI app; share `engine/` + `data/leaploop.db`.
11. ☐ Endpoints: `GET /api/roles` (triage/apply queues, filters), `POST /api/roles/{id}/decision` (yes/no/snooze/mute), `POST /api/roles/{id}/tailor` (→ engine.tailor+pdf), `POST /api/roles/{id}/applied` (toggle), `POST /api/generate` (manual JD/URL), `GET /api/health` (feed_health), `GET/PUT /api/settings` (filters/watchlist), `GET /api/pdf/{id}` (protected).
12. ☐ One-time **import the 74 applied** into `applied_index` (backup DB first).

## Cockpit — frontend (React/Vite) ☐
13. ☐ Scaffold Vite + React; bring in `theme.css` + lucide.
14. ☐ App shell (sidebar/topbar + mobile bottom-nav) + routing.
15. ☐ Screens, porting the reference: **home/inbox** → **triage** → **apply** → **tracker** → **generate** → **settings** → **login splash**.
16. ☐ Wire to API via TanStack Query; the swap-variant, applied-toggle, JD preview, copy-referral interactions.

## Deploy ☐ (Stage 3 deploy gate)
17. ☐ Dockerfile(s) + compose; port 8509; cron entry for watcher.
18. ☐ NPM proxy host + Cloudflare Tunnel route for `leaploop.vault7a.xyz`.
19. ☐ Authentik application + forward-auth; single user.
20. ☐ Secrets into `/opt/homeserver/leaploop/secrets.env`; GlitchTip wired (resolves `no-error-tracking`).
21. ☐ Smoke the 6 flows on the live URL.

## Deferred (not blocking)
- P5-D / P5-G cluster confirmations (resume-tuning pass).
- Tiering tuning pass.
