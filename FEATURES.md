<!-- generated from registry @ cccec71 on 2026-08-03 — DO NOT EDIT; edit the registry via the Ottomate API. R-DOC-1. -->
# leaploop — Features & Flows (generated reference)

> Generated from the Ottomate registry (the single source of truth). To change anything here, edit the feature/flow/acceptance-criteria in the tracker, then re-run `scripts/generation/gen-reference-docs.mjs --project leaploop`.

## Features

### done (13)

- **Apply queue** `feat-apply-queue` — _ui_, test: `not-tested`
  - PDF preview/download, apply link, swap-variant, copy referral, applied toggle (auto+manual).
  - AC: Each Apply card shows the tailored PDF (preview + download), the apply link, and an applied toggle (auto + manual). (test: `tests/test_engine.py::test_mark_applied_and_undo`)
  - AC: Swap-variant regenerates the PDF with a different P5/flex variant in one tap; Copy referral appears on warm-path roles.
- **ATS feed watcher** `feat-ats-watcher` — _automated_, test: `not-tested`
  - Polls Greenhouse/Lever/Ashby/Workday/amazon.jobs ~30 min; diffs new roles into the store.
  - AC: A poll of the configured ATS feeds completes and writes new roles to the store, recording ok/count/err per company in feed_health.
  - AC: Re-polling an unchanged feed adds no duplicate roles (dedupe on the source_id primary key).
- **Auth + deploy** `feat-auth-deploy` — _backend_, test: `not-tested`
  - Authentik SSO (single user), Docker on vault7a port 8509, NPM + Cloudflare Tunnel, cron watcher.
  - AC: The cockpit is reachable only at jobs.vault7a.xyz behind Authentik SSO (single user); the watcher runs on a 30-minute cron.
  - AC: Deployed as a Docker service on VAULT7A port 8509, fronted by NPM + Cloudflare Tunnel.
- **Cleaner / filter / dedupe** `feat-cleaner` — _automated_, test: `not-tested`
  - Dedupes across sources, applies config.py filters, drops already-applied via tracker cross-ref.
  - AC: A role already in the tracker as applied never reappears in Triage.
  - AC: The same role from two sources is shown once (dedupe by normalized company + title). (test: `tests/test_engine.py::test_find_active_by_company_normalizes_casing`)
- **Gmail auto-confirm applied** `feat-gmail-confirm` — _automated_, test: `not-tested`
  - Watches 'thanks for applying' emails; marks applied, drops from queue; manual override.
  - AC: A matching 'application received' email flips the role to applied with timestamp. (test: `tests/test_engine.py::test_company_from_confirmation_subject`)
  - AC: Manual override can set/clear applied regardless of email. (test: `tests/test_engine.py::test_mark_applied_and_undo`)
- **LinkedIn alert-email ingest** `feat-linkedin-ingest` — _automated_, test: `not-tested`
  - Reads jobalerts-noreply@linkedin.com via Gmail-IMAP; parses company/title/link as the daily backstop.
  - AC: A LinkedIn job-alert email from jobalerts-noreply@linkedin.com is parsed via Gmail-IMAP into role rows (company, title, link). (test: `tests/test_engine.py::test_parse_linkedin_extracts_title_company_url`)
  - AC: Runs as a daily backstop only - never drives or scrapes the LinkedIn site on a timer.
- **Manual Generate-PDF** `feat-manual-generate` — _hybrid_, test: `not-tested`
  - Paste JD text or role URL, bypass sourcing, produce a tailored PDF.
  - AC: Pasting JD text OR a role URL produces a tailored PDF, bypassing sourcing and filtering.
  - AC: Accepts text + URL only - no image/OCR and no file upload.
- **texlive PDF compile** `feat-pdf-compile` — _backend_, test: `not-tested`
  - Compiles the per-JD .tex via a texlive container to the constant-named PDF.
  - AC: Compiling a per-JD .tex yields a PDF byte-identical in layout to the Overleaf reference.
  - AC: Every output file is named Sai_Vardhan_Palli_Product_Manager_IIMB_CV.pdf.
- **Rules tailoring engine** `feat-rules-tailor` — _automated_, test: `not-tested`
  - Maps JD keywords to flex macros + P5 variant; writes per-JD .tex; safe-default fallback on low confidence.
  - AC: Given a JD mentioning payments/UPI, the engine selects the fintech-commission P5 + Domain skills append.
  - AC: On a JD with no confident cluster match, it falls back to the safe default master (never a wrong variant).
  - AC: Output .tex compiles without error and resolves all flex macros.
- **Settings / filter tuning** `feat-settings` — _ui_, test: `not-tested`
  - Edit role types/levels/excludes, watch-list/tiers, integration status, watcher health.
  - AC: Settings edits role types/levels/excludes, the watch-list and tiers, and shows integration + watcher health.
  - AC: Saved filter changes take effect on the next poll.
- **Reputability tiering** `feat-tiering` — _automated_, test: `not-tested`
  - Tags A/B/C/unverified via curated Tier-A list + Wikidata size/notability; ATS-presence as legitimacy signal.
  - AC: Every role is tagged A/B/C/U: curated TIER_A/TIER_B list first, else keyless Wikidata size/notability, else unverified (U). (test: `tests/test_engine.py::test_curated_tier_a_and_c`)
  - AC: A company with no curated or Wikidata match is flagged unverified, never silently dropped.
- **Application tracker** `feat-tracker` — _ui_, test: `not-tested`
  - Searchable record: company/role/resume PDF/date/source/status; CSV export.
  - AC: The tracker lists every application (company, role, which resume PDF, date, source, status) and is searchable.
  - AC: The list exports to CSV.
- **Triage queue** `feat-triage-queue` — _ui_, test: `not-tested`
  - Role cards with yes/no/snooze, preview JD, mute company; filter to Tier-A; sort by tier/age.
  - AC: Triage shows role cards (company, title, location/mode, tier badge, source, age) with Yes / No / Snooze, Preview JD, and Mute company.
  - AC: Cards can be filtered to Tier-A and sorted by tier or age.

## Flows

- **Apply to confirmed** `flow-apply-confirm` — test: `not-tested`
  - User opens Apply item → He applies on the ATS; Gmail confirmation auto-marks applied
- **Discovery to Triage** `flow-discovery-triage` — test: `not-tested`
  - Watcher poll / new alert email → Clean, tiered role appears in Triage; Tier-A roles are badged and sorted first
- **Filter tuning** `flow-filter-tune` — test: `not-tested`
  - User mutes a company / edits filters → Next poll respects the updated filters
- **Manual generate** `flow-manual-generate` — test: `not-tested`
  - User pastes JD text or role URL → Tailored PDF produced without sourcing/filtering
- **Tailor to PDF** `flow-tailor-pdf` — test: `not-tested`
  - User taps Yes (or manual submit) → Rules pick flex/P5, texlive compiles the constant-named PDF into Apply
- **Triage decision** `flow-triage-decision` — test: `not-tested`
  - User opens Triage queue → Yes enqueues tailoring; No skips; Snooze resurfaces later
