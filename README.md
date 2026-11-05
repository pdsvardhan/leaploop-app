# LeapLoop

> **About this public copy (November 2026).** LeapLoop is the job-hunt cockpit I built and use: it finds roles, scores the fit, and tailors my CV for each one. This is a single-commit snapshot of the code (from e9a2145 2026-09-12). My CV content, my real applications and some private notes are left out, and home-network addresses are replaced with documentation addresses (192.0.2.x). The live app is private.

Private, single-user PM job-hunt cockpit for Sai Vardhan Palli. **Shipped** — live at
`https://leaploop.vault7a.xyz` (Authentik SSO), built via Ottomate on VAULT7A.
Full spec: [LEAPLOOP_BRIEF.md](LEAPLOOP_BRIEF.md).

## Pipeline
`watcher` (ATS feeds + LinkedIn-email) → `cleaner` (filter/dedupe/drop-applied) → `tiering` (curated + Wikidata)
→ Triage (yes; Tier-A badged + sorted first) → `tailor` (rules: JD→flex/P5) → `pdf` (tectonic) → Apply queue → `gmail_confirm` (auto-applied).

> No notification/push channel: a Telegram Tier-A push was built then dropped (2026-06-04, adr-010). New roles surface only in the Triage queue.

## engine/
| file | role |
|---|---|
| `config.py` | locked filters + watch-list + A/B tiers |
| `feeds.py` | verified ATS feeds (Task A) + Greenhouse/Lever/amazon.jobs fetchers |
| `watcher.py` | poll all sources |
| `cleaner.py` | India-PM filter, exclude levels-out, dedupe, drop-applied, attach tier |
| `tiering.py` | curated A/B override + keyless Wikidata B/C; else U |
| `tailor.py` | deterministic JD→flex/P5 rules → per-JD `.tex` (+ fit hint, gaps) |
| `rules.yaml` | JD keyword clusters → flex overrides; honest-gap detector |
| `pdf.py` | compile `.tex` → constant-named PDF (tectonic / docker texlive) |
| `gmail_confirm.py` | IMAP: auto-confirm applied + LinkedIn-alert ingest |
| `run.py` | one poll cycle (cron entry) |

## resume/
`preamble.tex` + `body.tex` + `GENERIC.tex` — synced from the master at `Desktop/Resume/`. Edit fixed content there.

## Run
```bash
pip install -r requirements.txt
export LEAPLOOP_SECRETS=/opt/homeserver/leaploop/secrets.env
python -m engine.run                 # one poll cycle
python engine/tailor.py --text "...JD..." --out /tmp/cv.tex && tectonic /tmp/cv.tex
```

Secrets (Gmail app-password, Authentik client secret) live in `/opt/homeserver/leaploop/secrets.env` (chmod 600, never committed).
