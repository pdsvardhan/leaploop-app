"""Cockpit service layer: maps engine/DB rows to the shapes the React app expects, and
orchestrates on-demand tailoring (engine.tailor + engine.pdf). No web framework here."""
from __future__ import annotations
import json, os, re, time, urllib.request
from pathlib import Path

from engine import db, tailor, pdf, config, feeds, settings_store, cleaner

REPO = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("LEAPLOOP_DATA", REPO / "data"))
PDF_ROOT = DATA_DIR / "pdfs"

# JD-cluster <-> human variant label (the swap-variant control), derived from rules.yaml.
# It used to be a hand-kept list here, so a cluster added to rules.yaml never reached the
# dropdown and its label silently fell back to "Default (safe master)". Cached on the rules
# file's mtime: editing rules.yaml is picked up without a restart.
_VARIANT_CACHE: dict = {"mtime": None, "order": [], "n2l": {}, "l2n": {}}


def _variant_maps() -> dict:
    try:
        mtime = tailor.RULES_PATH.stat().st_mtime
    except OSError:
        mtime = None
    if _VARIANT_CACHE["mtime"] != mtime:
        opts = tailor.variant_options()
        _VARIANT_CACHE.update({
            "mtime": mtime,
            "order": [o["name"] for o in opts],
            "n2l": {o["name"]: o["label"] for o in opts},
            "l2n": {o["label"]: o["name"] for o in opts},
        })
    return _VARIANT_CACHE


def name_to_label(name: str | None, default_to_master: bool = True) -> str | None:
    m = _variant_maps()["n2l"]
    return m.get(name) or (m.get("default") if default_to_master else None)


def label_to_name(label: str | None) -> str | None:
    return _variant_maps()["l2n"].get(label) if label else None


def variant_labels() -> list[str]:
    m = _variant_maps()
    return [m["n2l"][n] for n in m["order"]]

UA = {"User-Agent": "Mozilla/5.0 (LeapLoop/1.0; personal job radar)"}

# applied_index.source written by the manual Generate screen. Undo only ever removes a row
# still carrying this source AND this token's résumé path.
MANUAL_SOURCE = "manual-generate"

# --- downloaded filename (adr-011) ------------------------------------------------
# The PDF on disk keeps config.PDF_OUTPUT_NAME. Only the name the BROWSER saves under
# varies, because Chrome refuses to overwrite an existing file and silently saves the
# second download of a sitting as "... CV (1).pdf" — and the ATS then uploads that name
# to the recruiter, which is the exact outcome the constant filename existed to prevent.
BASE_PDF_STEM = config.PDF_OUTPUT_NAME.rsplit(".", 1)[0]
MAX_COMPANY_SLUG = 24


def company_slug(company: str) -> str:
    """CamelCase-ish, filesystem-safe company token. 'Airtel Digital' -> 'AirtelDigital'."""
    return re.sub(r"[^A-Za-z0-9]+", "", company or "")[:MAX_COMPANY_SLUG]


def download_filename(company: str = "", con=None) -> str:
    """What the browser should save this PDF as. Falls back to the constant name when there
    is no company (the master one-pager) or when the owner has turned the setting off."""
    slug = company_slug(company)
    if not slug:
        return config.PDF_OUTPUT_NAME
    try:
        if not settings_store.get_settings(con or db.connect()).get("nameWithCompany", True):
            return config.PDF_OUTPUT_NAME
    except Exception:
        pass                      # a settings read must never break a download
    return f"{BASE_PDF_STEM}_{slug}.pdf"


def generated_company(token: str) -> str:
    """The company recorded for a manually generated PDF, if the owner supplied one."""
    return (_generated_meta(token).get("company") or "").strip()


# ----------------------------------------------------------------- formatting
def humanize_age(first_seen) -> str:
    if not first_seen:
        return "new"
    secs = max(0, time.time() - float(first_seen))
    if secs < 3600:
        return f"{int(secs // 60)}m"
    if secs < 86400:
        return f"{int(secs // 3600)}h"
    return f"{int(secs // 86400)}d"


def humanize_since(ts) -> str:
    if not ts:
        return "—"
    secs = max(0, time.time() - float(ts))
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _applied_company_set(con) -> set[str]:
    return {row[0] for row in con.execute("SELECT DISTINCT company_norm FROM applied_index")}


def role_card(r: dict, applied_cos: set[str]) -> dict:
    fs = r.get("first_seen")
    hrs = (time.time() - float(fs)) / 3600 if fs else 0
    gaps = [g for g in (r.get("gaps") or "").split(",") if g]
    has_jd = bool((r.get("jd_text") or "").strip())
    # fit_hint NULL means the role was never scored (no JD to score against). Emitting 0 there
    # claimed "scored, matched nothing" — a fabricated signal on 234 LinkedIn roles (item 886).
    # A JD-less role can still hold a non-null fit_hint: tailor_role falls back to scoring
    # "title + company" when jd_text is empty. That number describes the job title, not the job,
    # so it is not a fit score either — no JD, no score.
    scored = r.get("fit_hint") is not None and has_jd
    return {
        "id": r["source_id"],
        "co": r["company"],
        "role": r["title"],
        "loc": r.get("location") or "India",
        "mode": r.get("mode") or "",
        "source": r.get("source") or "ATS",
        "age": humanize_age(fs),
        "fresh": hrs < 12,
        "recent": db.norm(r["company"]) in applied_cos,
        "recruiter": cleaner.is_recruiter(r["company"]),   # third-party staffing listing flag
        "fit": int(r["fit_hint"]) if scored else None,  # transparent theme-overlap count, NOT a rank
        "scored": scored,
        "gaps": gaps,
        "hasJd": has_jd,        # Preview JD only when there's a JD to show
        # Discovery-only: found for you, but nothing here can be tailored without a JD.
        # LinkedIn alerts carry no description and fetching the page would breach the
        # no-scraping rail, so the honest move is to say so (item 886).
        "discoveryOnly": not has_jd,
        "tier": r.get("tier") or "U",
        "url": r.get("url") or "",
        # None until something was actually tailored. Defaulting to "Default (safe master)"
        # implied a tailoring choice had been made for every untouched role.
        "variant": r.get("variant") or None,
        "variants": variant_labels(),
        "applied": bool(r.get("applied")),
        "appliedAt": r.get("applied_at"),
        "pdfReady": bool(r.get("pdf_path")),
    }


def list_queue(con, queue: str) -> list[dict]:
    applied_cos = _applied_company_set(con)
    if queue == "triage":
        rows = con.execute(
            "SELECT * FROM roles WHERE state='triage' OR (state='snoozed' AND COALESCE(snoozed_until,0) <= ?) "
            "ORDER BY first_seen DESC", (time.time(),))
        cards = [role_card(dict(r), applied_cos) for r in rows]
        return _cap_per_company(cards)
    elif queue == "apply":
        rows = con.execute(
            "SELECT * FROM roles WHERE state IN ('picked','applied') ORDER BY updated DESC")
    elif queue == "tracker":
        rows = con.execute(
            "SELECT * FROM roles WHERE applied=1 ORDER BY applied_at DESC")
    else:
        rows = con.execute("SELECT * FROM roles ORDER BY first_seen DESC")
    return [role_card(dict(r), applied_cos) for r in rows]


def _cap_per_company(cards: list[dict]) -> list[dict]:
    """Show at most MAX_PER_COMPANY_TRIAGE roles per company so one employer can't flood Triage."""
    cap = getattr(config, "MAX_PER_COMPANY_TRIAGE", 6)
    per, out = {}, []
    for c in cards:
        per[c["co"]] = per.get(c["co"], 0) + 1
        if per[c["co"]] <= cap:
            out.append(c)
    return out


def tracker_rows(con) -> list[dict]:
    """Applied applications for the Tracker screen (roles + the one-time imported history)."""
    out = []
    for r in con.execute("SELECT * FROM roles WHERE applied=1 ORDER BY applied_at DESC"):
        r = dict(r)
        out.append({"co": r["company"], "role": r["title"],
                    "resume": Path(r["pdf_path"]).name if r.get("pdf_path") else config.PDF_OUTPUT_NAME,
                    "date": r.get("applied_at") or "", "source": r.get("source") or "ATS",
                    "status": "applied", "tier": r.get("tier") or "U"})
    # historical applied_index rows that have no live role (the imported 74)
    live = {(db.norm(o["co"]), db.norm(o["role"])) for o in out}
    for a in con.execute("SELECT * FROM applied_index ORDER BY date DESC"):
        a = dict(a)
        if (a["company_norm"], a["title_norm"]) in live:
            continue
        if not a["company_norm"]:
            continue
        out.append({"co": a["company_norm"].title(), "role": (a["title_norm"] or "Product Manager").title(),
                    "resume": a.get("resume") or "—", "date": a.get("date") or "",
                    "source": a.get("source") or "import", "status": "applied", "tier": "U"})
    return out


# ----------------------------------------------------------------- tailoring
def pdf_dir_for(key: str, create: bool = True) -> Path:
    """Directory for one key's artefacts. `create=False` for read/lookup paths — mkdir on a
    read meant a bogus token littered data/pdfs with empty directories."""
    d = PDF_ROOT / re.sub(r"\W+", "_", key)[:80]
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def tailor_role(source_id: str, force_variant: str | None = None) -> dict | None:
    """Render + compile the tailored PDF for a role. Opens its own DB connection (background-safe)."""
    con = db.connect()
    r = con.execute("SELECT * FROM roles WHERE source_id=?", (source_id,)).fetchone()
    if not r:
        return None
    r = dict(r)
    # The role title is scored separately at TITLE_WEIGHT (iter-170). The old fallback string
    # "<title> <company>" only existed to give a JD-less role something to score; the title
    # now carries that on its own and the company name never held a keyword anyway.
    jd = r.get("jd_text") or ""
    force_name = label_to_name(force_variant) if force_variant else None
    res = tailor.render_tex(jd, force_cluster=force_name, title=r.get("title") or "")
    d = pdf_dir_for(source_id)
    tex = d / "cv.tex"
    tex.write_text(res["tex"], encoding="utf-8")
    out_pdf = pdf.compile_tex(tex, config.PDF_OUTPUT_NAME)
    # Store the path RELATIVE to the data dir so it resolves the same on host or in the
    # container (where /mnt/.../data is mounted at /data). resolve_pdf() rebuilds the absolute path.
    rel = str(out_pdf.relative_to(DATA_DIR)) if str(out_pdf).startswith(str(DATA_DIR)) else str(out_pdf)
    label = name_to_label(res["cluster"])
    # A fresh tailor supersedes any saved chip edits — keeping them would make the editor
    # reopen with values that no longer describe the PDF on screen.
    con.execute(
        "UPDATE roles SET variant=?, pdf_path=?, fit_hint=?, gaps=?, overrides_json=NULL, "
        "updated=? WHERE source_id=?",
        (label, rel, res["fit_hint"], ",".join(res["gaps_triggered"]), time.time(), source_id))
    con.commit()
    return {"variant": label, "pdf_path": rel, "cluster": res["cluster"],
            "fit": res["fit_hint"], "gaps": res["gaps_triggered"],
            "warnings": resume_warnings(con)}


def resolve_pdf(path_str: str) -> Path | None:
    """Resolve a stored pdf_path to an existing file. Handles relative paths and legacy
    absolute paths written under a different data root (host vs container)."""
    if not path_str:
        return None
    p = Path(path_str)
    if not p.is_absolute():
        p = DATA_DIR / p
    if p.exists():
        return p
    # legacy absolute path from a different data root: relocate by its parent folder name
    cand = PDF_ROOT / Path(path_str).parent.name / config.PDF_OUTPUT_NAME
    return cand if cand.exists() else None


RESUME_DIR = Path(os.environ.get("LEAPLOOP_RESUME_DIR", REPO / "resume"))


def master_resume_pdf() -> Path:
    """The default/master résumé (no JD tailoring) — the clean in-hand one-pager for socials +
    referrals. Compiled once and cached; recompiled if the resume source OR rules.yaml changes
    (the master takes its 5th bullet and descriptor from the rules `default` block, so a rules
    edit used to leave a stale master PDF served indefinitely)."""
    d = pdf_dir_for("_master")
    out = d / config.PDF_OUTPUT_NAME
    src_mtime = _master_source_mtime()
    if out.exists() and out.stat().st_mtime >= src_mtime:
        return out
    res = tailor.render_tex("", force_cluster="default")
    (d / "cv.tex").write_text(res["tex"], encoding="utf-8")
    return pdf.compile_tex(d / "cv.tex", config.PDF_OUTPUT_NAME)


# Hosts we must never fetch. LinkedIn is a locked non_goal ("LinkedIn scraping or driving the
# site on a timer"), and the verifier caught the Tailor-from-JD hand-off routing job URLs
# straight into urlopen() below. It also never worked — LinkedIn serves a login wall — so the
# refusal costs nothing and the guard belongs at the fetch boundary, not in the caller.
NO_FETCH_HOSTS = ("linkedin.com", "www.linkedin.com")


def is_blocked_fetch_host(url: str) -> bool:
    from urllib.parse import urlparse
    host = (urlparse(url or "").hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in NO_FETCH_HOSTS)


def fetch_jd_from_url(url: str) -> str:
    """Best-effort JD text from a role URL. Greenhouse/Lever have JSON; else strip the page HTML.

    Returns "" for blocked hosts without making any request.
    """
    if is_blocked_fetch_host(url):
        return ""
    try:
        m = re.search(r"greenhouse\.io.*/jobs/(\d+)|boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
        if "greenhouse" in url and m:
            jid = m.group(1) or m.group(3)
            board = m.group(2) or re.search(r"greenhouse\.io/([^/]+)", url).group(1)
            import json
            data = json.loads(_get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}"))
            return feeds._strip_html(data.get("content", ""))
        if "lever.co" in url:
            import json
            slug = re.search(r"lever\.co/([^/]+)/([0-9a-f-]+)", url)
            if slug:
                data = json.loads(_get(f"https://api.lever.co/v0/postings/{slug.group(1)}/{slug.group(2)}?mode=json"))
                return feeds._strip_html(data.get("descriptionPlain") or data.get("description", ""))
        html = _get(url)
        return feeds._strip_html(html)[:8000]
    except Exception:
        return ""


def _get(url: str, timeout=20) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ----------------------------------------------------------------- generated-PDF metadata
def _generated_meta_path(token: str) -> Path:
    return pdf_dir_for(f"_generated/{token}", create=False) / "meta.json"


def _generated_pdf_rel(token: str) -> str | None:
    """The stored-relative path of a generated PDF, or None if it is not on disk."""
    p = pdf_dir_for(f"_generated/{token}", create=False) / config.PDF_OUTPUT_NAME
    return str(p.relative_to(DATA_DIR)) if p.exists() else None


def _generated_meta(token: str) -> dict:
    try:
        return json.loads(_generated_meta_path(token).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_generated_meta(token: str, meta: dict) -> None:
    try:
        p = _generated_meta_path(token)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    except OSError:
        pass


def generate_pdf(text: str = "", url: str = "", company: str = "", title: str = "") -> dict:
    """Manual generate: tailor a PDF from pasted JD text OR a role URL. No sourcing/filtering.

    `company` / `title` are optional and only used to label the result and, if the user later
    clicks "Log as applied", to write the dedupe row (see log_generated_applied).
    """
    jd = (text or "").strip()
    fetched_from = None
    if not jd and url:
        if is_blocked_fetch_host(url):
            return {"ok": False, "blocked_host": True,
                    "error": "LeapLoop never fetches LinkedIn pages. Open the posting yourself "
                             "and paste the job description here."}
        jd = fetch_jd_from_url(url)
        fetched_from = url
    if not jd or len(jd) < 40:
        return {"ok": False, "error": "Could not read a job description. Paste the JD text instead."}
    title = (title or "").strip()
    company = (company or "").strip()
    res = tailor.render_tex(jd, title=title)
    token = re.sub(r"\W+", "", str(time.time()))
    d = pdf_dir_for(f"_generated/{token}")
    tex = d / "cv.tex"
    tex.write_text(res["tex"], encoding="utf-8")
    out_pdf = pdf.compile_tex(tex, config.PDF_OUTPUT_NAME)
    # Remember which cluster produced this PDF. Without it the editor reseeded its chips from
    # "default" every time, so opening Edit -> Quick edit -> Recompile silently threw the
    # tailoring away and handed back the default master.
    _write_generated_meta(token, {"cluster": res["cluster"], "company": company, "title": title,
                                  "apply_url": url or None, "created": time.time()})
    return {"ok": True, "token": token, "pdf_path": str(out_pdf),
            "variant": name_to_label(res["cluster"]),
            "cluster": res["cluster"], "fit": res["fit_hint"], "company": company, "title": title,
            "gaps": res["gaps_triggered"], "apply_url": url or None, "fetched_from": fetched_from,
            "warnings": resume_warnings(db.connect())}


def log_generated_applied(token: str, company: str = "", title: str = "") -> dict:
    """Record a manually generated CV as applied so the role stops resurfacing in Triage.

    To-do #420 asked for this write to happen inside generate_pdf. It does not: generating a
    PDF is not applying, and an automatic write would fill applied_index — and therefore the
    Tracker — with roles that were never sent. The Generate screen offers it as one explicit
    click instead, which closes the same dedupe hole (cleaner.py:120 drops anything already in
    applied_index) without inventing an application that never happened.
    """
    meta = _generated_meta(token)
    company = (company or meta.get("company") or "").strip()
    title = (title or meta.get("title") or "").strip() or "Product Manager"
    if not company:
        return {"ok": False, "error": "Add the company name — that is what the dedupe matches on."}
    con = db.connect()
    # Never write over a row that is already there. add_applied is INSERT OR REPLACE on
    # (company_norm, title_norm), so logging a company you had already applied to would have
    # silently replaced a real gmail-confirm or imported row's résumé, source and date.
    already = db.already_applied(con, company, title)
    if not already:
        # Record THIS résumé, not the constant filename, and only if it is actually on disk.
        db.add_applied(con, company, title,
                       resume=_generated_pdf_rel(token) or config.PDF_OUTPUT_NAME,
                       source=MANUAL_SOURCE)
    meta.update({"company": company, "title": title,
                 "applied_at": time.strftime("%Y-%m-%d %H:%M")})
    _write_generated_meta(token, meta)
    return {"ok": True, "company": company, "title": title, "already_tracked": already}


def _row_belongs_to(row: dict | None, token: str) -> bool:
    """Does this applied_index row still hold what THIS token wrote?

    Ownership is read off the row at undo time rather than remembered from the write. Both
    gmail_confirm and the Apply screen write with INSERT OR REPLACE on the same primary key,
    so a row we created can be replaced by a genuine confirmation — and deleting that would
    repeat the data loss this whole guard exists to prevent, just more narrowly.
    """
    if not row or row.get("source") != MANUAL_SOURCE:
        return False
    return f"_generated_{token}" in (row.get("resume") or "")


def unlog_generated_applied(token: str) -> dict:
    """Undo log_generated_applied — only for a row that is still this token's own.

    The first version deleted on (company_norm, title_norm) with no ownership check at all, so
    an undo could erase an application it had nothing to do with. 48 of the 54 rows in the live
    applied_index have no matching role (the one-time import), which makes applied_index the
    only record they exist in — deleting one there loses it for good.
    """
    meta = _generated_meta(token)
    company, title = (meta.get("company") or "").strip(), (meta.get("title") or "").strip()
    if not meta.get("applied_at") or not company:
        return {"ok": False, "error": "Nothing was logged for this résumé."}
    title = title or "Product Manager"
    con = db.connect()
    mine = _row_belongs_to(db.get_applied(con, company, title), token)
    removed = db.remove_applied(con, company, title) if mine else 0
    meta.pop("applied_at", None)
    meta.pop("wrote_row", None)          # legacy key from the first version of this guard
    _write_generated_meta(token, meta)
    return {"ok": True, "removed": removed, "company": company, "kept_existing": not mine}


# ----------------------------------------------------------------- per-JD editor (item 307)
def _seed_overrides(cluster_name: str, rules: dict) -> dict:
    name = label_to_name(cluster_name) or cluster_name   # accept a label or a raw name
    if name not in {c["name"] for c in rules.get("clusters", [])} and name != "default":
        name = "default"
    return tailor.overrides_for_cluster(name, rules)


def _saved_overrides(blob) -> dict | None:
    """A previously saved chip-edit dict, or None. Stored raw (unescaped) so it survives a
    round-trip through the editor."""
    if not blob:
        return None
    try:
        d = json.loads(blob)
        return d if isinstance(d, dict) and d else None
    except Exception:
        return None


def role_edit_state(source_id: str) -> dict | None:
    """Seed the resume editor for an Apply-queue role: current .tex + chip-editor fields."""
    con = db.connect()
    r = con.execute("SELECT * FROM roles WHERE source_id=?", (source_id,)).fetchone()
    if not r:
        return None
    r = dict(r)
    rules = tailor.load_rules()
    label = r.get("variant") or name_to_label("default")
    # create=False: this is a lookup. Opening the editor for an unknown role used to
    # leave an empty directory behind under data/pdfs.
    texf = pdf_dir_for(source_id, create=False) / "cv.tex"
    tex = texf.read_text(encoding="utf-8") if texf.exists() else \
        tailor.render_tex(r.get("jd_text") or "", force_cluster=label_to_name(label) or "default",
                          title=r.get("title") or "")["tex"]
    # Reseed from the user's own last chip edit when there is one. Without this, one edit set
    # variant to "Custom (edited)" — a label that maps to no cluster — so the next open fell
    # back to the default chips and quietly dropped everything the user had typed.
    saved = _saved_overrides(r.get("overrides_json"))
    return {"id": source_id, "variant": label,
            "overrides": saved or _seed_overrides(label, rules), "custom": bool(saved),
            "p5_options": tailor.p5_options(rules), "tex": tex}


def _recompile_into(dirkey: str, jd_text: str, mode: str, overrides: dict | None, tex: str | None) -> dict:
    """Shared recompile for both roles and generated PDFs. Writes cv.tex, compiles (never raises),
    returns {ok, error?, tex?, pdf_rel?}. mode='tex' compiles raw LaTeX; 'chips' builds from flex fields."""
    d = pdf_dir_for(dirkey)
    texf = d / "cv.tex"
    saved_ov = None
    notes: list[str] = []
    if mode == "tex":
        if not tex or "\\begin{document}" not in tex or "\\end{document}" not in tex:
            return {"ok": False, "error": "That doesn't look like a complete LaTeX document (missing \\begin/\\end{document})."}
        out_tex = tex
    else:
        ov = tailor.sanitize_override(overrides or {}, notes=notes)
        out_tex = tailor.render_tex(jd_text or "", override=ov)["tex"]
        saved_ov = ov
    texf.write_text(out_tex, encoding="utf-8")
    out_pdf, log = pdf.compile_tex_safe(texf)
    if not out_pdf:
        return {"ok": False, "error": log[-1400:] or "LaTeX compile failed."}
    rel = str(out_pdf.relative_to(DATA_DIR)) if str(out_pdf).startswith(str(DATA_DIR)) else str(out_pdf)
    return {"ok": True, "tex": out_tex, "pdf_rel": rel, "overrides": saved_ov, "notes": notes}


def recompile_role(source_id: str, mode: str = "chips", overrides: dict | None = None,
                   tex: str | None = None) -> dict | None:
    con = db.connect()
    r = con.execute("SELECT * FROM roles WHERE source_id=?", (source_id,)).fetchone()
    if not r:
        return None
    r = dict(r)
    res = _recompile_into(source_id, r.get("jd_text") or "", mode, overrides, tex)
    if not res.get("ok"):
        return res
    if res.get("overrides") is not None:
        con.execute("UPDATE roles SET variant=?, pdf_path=?, overrides_json=?, updated=? "
                    "WHERE source_id=?",
                    ("Custom (edited)", res["pdf_rel"], json.dumps(res["overrides"]),
                     time.time(), source_id))
    else:
        # Raw-.tex edit: the .tex is now the authority, so the saved chip values stay as they
        # were rather than being invented from a document nobody parsed.
        con.execute("UPDATE roles SET variant=?, pdf_path=?, updated=? WHERE source_id=?",
                    ("Custom (edited)", res["pdf_rel"], time.time(), source_id))
    con.commit()
    return {"ok": True, "variant": "Custom (edited)", "notes": res.get("notes") or []}


def generated_edit_state(token: str) -> dict | None:
    rules = tailor.load_rules()
    texf = pdf_dir_for(f"_generated/{token}", create=False) / "cv.tex"
    if not texf.exists():
        return None
    # Seed from what actually produced this PDF — the saved chip edit first, then the cluster
    # the generator chose. Hardcoding "default" here is what made Edit -> Recompile revert a
    # tailored CV to the plain master without a word of warning.
    meta = _generated_meta(token)
    saved = _saved_overrides(json.dumps(meta.get("overrides")) if meta.get("overrides") else None)
    return {"token": token,
            "overrides": saved or _seed_overrides(meta.get("cluster") or "default", rules),
            "custom": bool(saved), "variant": name_to_label(meta.get("cluster") or "default"),
            "p5_options": tailor.p5_options(rules), "tex": texf.read_text(encoding="utf-8")}


def recompile_generated(token: str, mode: str = "chips", overrides: dict | None = None,
                        tex: str | None = None) -> dict:
    texf = pdf_dir_for(f"_generated/{token}", create=False) / "cv.tex"
    if not texf.exists():
        return {"ok": False, "error": "This generated résumé has expired — regenerate it first."}
    res = _recompile_into(f"_generated/{token}", "", mode, overrides, tex)
    if not res.get("ok"):
        return res
    if res.get("overrides") is not None:
        meta = _generated_meta(token)
        meta["overrides"] = res["overrides"]
        _write_generated_meta(token, meta)
    return {"ok": True, "token": token, "pdf_url": f"/api/pdf/generated/{token}",
            "notes": res.get("notes") or []}


# ----------------------------------------------------------------- health
def _feed_pretty(co: str) -> str:
    meta = feeds.FEEDS.get(co)
    if meta:
        return f"{co.title()} ATS ({meta['ats'].title()})"
    return co.title()


def health_payload(con) -> dict:
    rows = [dict(r) for r in con.execute("SELECT * FROM feed_health ORDER BY company")]
    feed_list = [{"name": _feed_pretty(r["company"]), "kind": "ATS", "ok": bool(r["ok"]),
                  "last": humanize_since(r["last"]), "count": r["count"], "err": r["err"]}
                 for r in rows]
    last_poll = max([r["last"] for r in rows] or [0])
    new_today = con.execute("SELECT count(*) FROM roles WHERE first_seen > ?",
                            (time.time() - 86400,)).fetchone()[0]
    return {"lastPoll": humanize_since(last_poll), "newToday": new_today,
            "feeds": feed_list, "brokenFeeds": sum(1 for f in feed_list if not f["ok"])}


INTEGRATION_LEGS = {
    "gmail-confirm": "Gmail auto-confirm (applied)",
    "linkedin-ingest": "LinkedIn alert ingest",
}
# A leg that has not succeeded in this long is reported failed rather than merely degraded.
INTEGRATION_STALE_SECS = 6 * 3600


def _integration_leg(name: str, configured: bool, h: dict | None) -> dict:
    """Derive an honest status for one integration leg.

    'configured' only ever meant "a credential exists". It stayed true through weeks of
    Gmail FETCH failures, which is how the dead auto-confirm went unnoticed (item 885).
    """
    row = {
        "name": name,
        "label": INTEGRATION_LEGS.get(name, name),
        "configured": configured,
        "lastAttempt": humanize_since(h["last_attempt"]) if h and h.get("last_attempt") else "—",
        "lastSuccess": humanize_since(h["last_success"]) if h and h.get("last_success") else "never",
        "lastError": (h or {}).get("last_error") or None,
    }
    if not configured:
        row["status"] = "not-configured"
    elif not h or not h.get("last_attempt"):
        row["status"] = "unknown"          # credentials exist, never run since this shipped
    elif h.get("ok"):
        row["status"] = "ok"
    elif h.get("last_success") and (time.time() - float(h["last_success"])) < INTEGRATION_STALE_SECS:
        row["status"] = "degraded"         # failing now, but worked recently
    else:
        row["status"] = "failed"
    row["healthy"] = row["status"] in ("ok", "unknown")
    return row


def integration_status(con) -> dict:
    """Honest integration state for Settings — real last-success/last-error, not just config."""
    from engine import gmail_confirm
    g = gmail_confirm._secrets()
    configured = bool(g.get("GMAIL_USER") and g.get("GMAIL_APP_PASSWORD"))
    rows = {r["name"]: r for r in db.get_integrations(con)}
    legs = [_integration_leg(n, configured, rows.get(n)) for n in INTEGRATION_LEGS]
    return {
        # legacy key kept so an older Settings build keeps rendering
        "gmail": {"configured": configured},
        "legs": legs,
        "broken": [l["name"] for l in legs if not l["healthy"]],
    }


# ----------------------------------------------------------------- résumé freshness (item 888)
MASTER_REVIEW_KEY = "resume_master_reviewed"
# An open-ended employment range needs re-confirming this often. The real failure: the owner
# left HSBC in June 2026 and body.tex still read "Jul 2024 -- Present" months later, so every
# generated CV carried a false date and nothing in the system objected.
MASTER_REVIEW_INTERVAL_DAYS = 60
_OPEN_ENDED_RE = re.compile(r"(?:--|–|—|-)\s*Present\b", re.I)


def _master_source_mtime() -> float:
    """Newest mtime across everything the master PDF is built from."""
    mtimes = [p.stat().st_mtime for p in RESUME_DIR.glob("*.tex")]
    try:
        mtimes.append(tailor.RULES_PATH.stat().st_mtime)
    except OSError:
        pass
    return max(mtimes, default=0.0)


def _open_ended_entries() -> list[str]:
    """Employment ranges in the master that are still open-ended ('... -- Present')."""
    body = RESUME_DIR / "body.tex"
    if not body.exists():
        return []
    out = []
    for line in body.read_text(encoding="utf-8", errors="replace").splitlines():
        if _OPEN_ENDED_RE.search(line):
            m = re.search(r"\\entry\{([^}]*)\}", line)
            out.append(m.group(1).replace("---", "—").strip() if m else line.strip()[:80])
    return out


def master_review_state(con) -> dict:
    from engine import settings_store
    st = settings_store.get_status(con, MASTER_REVIEW_KEY) or {}
    return {"reviewed_at": st.get("at"), "reviewed_note": st.get("note")}


def mark_master_reviewed(con, note: str = "") -> dict:
    from engine import settings_store
    settings_store.set_status(con, MASTER_REVIEW_KEY, {"at": time.time(), "note": note[:200]})
    return master_review_state(con)


def resume_warnings(con) -> list[dict]:
    """Warnings to show at generate time. WARN only — the PDF is still produced (owner's call)."""
    warnings = []
    reviewed_at = (master_review_state(con) or {}).get("reviewed_at")
    open_ended = _open_ended_entries()
    src_mtime = _master_source_mtime()

    if open_ended:
        age_days = (time.time() - float(reviewed_at)) / 86400 if reviewed_at else None
        if age_days is None or age_days > MASTER_REVIEW_INTERVAL_DAYS:
            warnings.append({
                "level": "warn",
                "code": "master-open-ended-unreviewed",
                "message": (
                    "Your résumé still shows an open-ended role — "
                    + "; ".join(open_ended[:3])
                    + (". You have never confirmed this is current."
                       if age_days is None else
                       f". Last confirmed {int(age_days)} days ago.")
                    + " Check the end date before sending this."
                ),
            })
    if reviewed_at and src_mtime and float(reviewed_at) < src_mtime:
        warnings.append({
            "level": "info",
            "code": "master-edited-since-review",
            "message": "The résumé master was edited after you last confirmed it.",
        })
    return warnings
