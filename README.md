# LeapLoop

LeapLoop is the app I built for my own job search for product-manager roles in India. It watches job feeds, filters and tiers the roles, tailors a one-page LaTeX CV to each job description, and keeps the work in two queues in a web "cockpit": Triage (yes or no) and Apply.

It is a single-user, self-hosted tool, not a product for others.

## About this public copy

- This repo is a single-commit snapshot of the code, published in November 2026.
- My CV content (`resume/body.tex`, `resume/GENERIC.tex`), my real applications (`cockpit/api/applied_seed.json` is empty), my private notes in `engine/rules.yaml` and the development log are left out.
- The live app is private, behind my own sign-in, so there is no demo link.

## What it does

1. **Find roles.** Each cycle (`python -m engine.run`) polls the public job-board APIs of 18 companies on Greenhouse, Lever, Ashby and amazon.jobs ([engine/feeds.py](engine/feeds.py)). It also reads LinkedIn job-alert emails from Gmail and pulls out the title, company and link. It never opens LinkedIn pages, so those roles have no job description. On my server, cron runs [run_cycle.sh](run_cycle.sh) every 30 minutes.
2. **Clean and dedupe.** [engine/cleaner.py](engine/cleaner.py) keeps product-manager titles in India. It drops excluded words (intern, contract, program manager and others), senior levels (lead, principal, director and up), and roles whose description asks for more than 6 years of experience. It also removes duplicates by company and title, reposts of stored roles, muted companies, and roles I have already applied to.
3. **Tier companies.** A tier is a rough reputation label for the employer: A (top), B, C or U (unverified). [engine/tiering.py](engine/tiering.py) checks my Settings first, then the curated lists in [engine/config.py](engine/config.py). If a company is on neither, it looks it up on Wikidata (no API key needed): 1,000 or more employees gives B, a smaller or unknown size gives C, and no match gives U. Unverified companies are flagged, never dropped.
4. **Triage.** New roles land in the Triage queue. Each card shows the tier, source, age and a "fit hint": how many keywords from the best-matching rules cluster appear in the job description or title. It is a plain count, not a ranking. I can say Yes, No, Snooze (12 hours) or Mute company, preview the job description, filter to Tier A, and sort by tier, fit or age. No, Snooze and Mute also work in bulk. Yes does not, because each Yes starts a CV build.
5. **Tailor the CV.** A Yes starts tailoring in the background. [engine/tailor.py](engine/tailor.py) reads the job description and title, picks a set of rules, and writes a `.tex` file for that job. The next section explains how.
6. **Compile the PDF.** [engine/pdf.py](engine/pdf.py) compiles the `.tex` file with tectonic. If tectonic is not installed, it falls back to `pdflatex` in a TeX Live Docker container. The PDF always has the same file name (set in `config.py`); the downloaded copy can add the company name.
7. **Apply queue.** The Apply screen shows the PDF (preview and download) and the apply link. I can rebuild the PDF with a different set of rules, edit it (simple fields or raw LaTeX), copy a referral message draft, and mark the role as applied. I apply on the company site myself; nothing is submitted automatically. A separate Generate screen tailors a CV from pasted job text or a job URL, outside the queues (LinkedIn links are refused).
8. **Confirm from email.** Each cycle, [engine/gmail_confirm.py](engine/gmail_confirm.py) searches the last 3 days of Gmail for subjects like "thanks for applying". It guesses the company from the subject or sender, marks the matching role I said Yes to as applied, and records it so the role does not come back. Mailbox access is read-only. A Tracker screen lists all applications, with search and CSV export.

## How the CV tailoring works

The CV is one LaTeX document built from [resume/preamble.tex](resume/preamble.tex) (layout and macros) and `resume/body.tex` (the content). The preamble defines a few "flex" macros, which are the only parts that change per job: a short descriptor in the summary, one swappable work bullet, extra skill tags, an optional education bullet, and the choice of a third project.

[engine/rules.yaml](engine/rules.yaml) holds seven keyword clusters: fintech and payments, e-commerce, platform and B2B, AI-native, data product, banking and compliance, and agile delivery. Each cluster says what to put in the flex macros. The engine scores every cluster against the job description:

- A keyword counts only as a whole word, and a hit in the job title counts three times.
- Topic clusters come first. The agile-delivery cluster describes ways of working, so it is used only when no topic cluster matches.
- If nothing matches, the CV stays the default master. There is no AI model in this loop, so the same input always gives the same CV.

The swappable bullet is the fifth bullet under my most recent job, called "P5" in the code. The rules file holds seven true versions of it, and each cluster picks one. The rules file can also list "honest gaps": skills a job asks for that my CV cannot back up. They show as a caution on the role and are never added to the CV. That list is empty in this copy.

The engine writes its choices as `\renewcommand` lines between the preamble and the body, then compiles the result with tectonic.

## Tech stack

- **Engine:** Python (3.12 in the Docker image), mostly standard library plus PyYAML. Data lives in one SQLite file.
- **API:** FastAPI, Uvicorn and Pydantic. The API imports `engine/` directly and also serves the built web app.
- **Web:** React 18, Vite 5 and TanStack Query, with hand-written CSS.
- **PDF:** LaTeX compiled by tectonic, with a TeX Live Docker image as a fallback.
- **Packaging:** one multi-stage Docker image (Node 20 builds the web app, Python 3.12 runs it).
- **Tests and CI:** pytest in `tests/`, and a Gitea Actions workflow in `.gitea/workflows/ci.yml`.
- **My hosting:** a home server, with Cloudflare Tunnel, Nginx Proxy Manager and Authentik single sign-on in front. The app has no login of its own, so do not expose it without an auth proxy.

## Running it

The repo is set up for my server, so expect to adapt it. You need:

- **Your own CV in `resume/`.** At minimum a `body.tex` written with the macros in `preamble.tex`; see [resume/README.md](resume/README.md). Without it, tailoring fails, and the Docker build stops at the step that compiles the CV once to cache LaTeX packages.
- **tectonic or Docker** on the machine that compiles PDFs (the Docker image installs tectonic for you).
- **Gmail secrets (optional):** `GMAIL_USER` and `GMAIL_APP_PASSWORD`, for the LinkedIn-alert and confirmation steps. They are read from the environment or from the `KEY=value` file named by `LEAPLOOP_SECRETS`. Without them those two steps are skipped (Settings shows them as not configured); the job feeds still work.
- **Optional settings, all with defaults:** `LEAPLOOP_DB` (SQLite file), `LEAPLOOP_DATA` (PDF folder), `LEAPLOOP_RESUME_DIR`, `LEAPLOOP_WEB_DIST`, `LEAPLOOP_TEX_CONTAINER` and `LEAPLOOP_TEX_IMAGE` (Docker fallback), and `GLITCHTIP_DSN` or `SENTRY_DSN` (error tracking; needs `sentry-sdk`, which is not in the requirements).

**With Docker:** [docker-compose.yml](docker-compose.yml) builds the image and serves the cockpit on `127.0.0.1:8509`. As written, it mounts my server paths for data and secrets and joins an external `authentik-net` network. Change those first, then run `docker compose up -d --build`. The container runs only the web app; schedule `python -m engine.run` separately to poll for roles.

**Without Docker:**

```bash
pip install -r requirements.txt -r cockpit/requirements.txt
(cd cockpit/web && npm ci && npm run build)
python -m engine.run                                 # one poll cycle
python -m uvicorn cockpit.api.main:app --port 8509   # cockpit at http://127.0.0.1:8509
python engine/tailor.py --text "...job description..." --out cv.tex && tectonic cv.tex   # tailoring only
```

Run the tests with `pytest` from the repo root. In this copy, five tests fail until you add your own `resume/body.tex` and `honest_gaps` entries; the rest pass.

## What's in this repo

| Folder | What it holds |
|---|---|
| `engine/` | The Python pipeline: feeds, cleaner, tiering, tailoring rules, PDF compile, Gmail steps, SQLite store, settings |
| `cockpit/api/` | FastAPI backend: queues, decisions, tailoring, CV editor, PDF serving, settings, health |
| `cockpit/web/` | React app: Home, Triage, Apply, Tracker, Generate and Settings screens |
| `resume/` | LaTeX layout and macros (`preamble.tex`); your CV content goes here |
| `tests/` | pytest tests for the engine and the API service layer |
| `scripts/` | Setup scripts for my server (Authentik, Nginx Proxy Manager, Ottomate tracker), one-off data fixes, and the import of past applications |
| `architecture/` | Mermaid diagrams of the data flow and hosting |
| `ottomate/` | The project spec from Ottomate: overview, features, flows, UI, risks, data sources and decision records |
| `public_docs/` | Short write-ups: thesis, technical deep-dive, validation and retrospective |

[FEATURES.md](FEATURES.md), [ARCHITECTURE.md](ARCHITECTURE.md), [BUILD_PLAN.md](BUILD_PLAN.md) and [CODING_GUIDELINES.md](CODING_GUIDELINES.md) are design documents from the build. Some details in them are dated, such as a Telegram alert that was built and later removed.

## Links

- Author: [Sai Vardhan Palli](https://www.linkedin.com/in/sai-vardhan-palli-3b1614187/) on LinkedIn.
- LeapLoop was built with Ottomate, my staged pipeline for specifying, building and verifying web projects. The `ottomate/` folder holds the spec it produced. More at the [Ottomate showcase](https://ottomate.vault7a.xyz/showcase/).
