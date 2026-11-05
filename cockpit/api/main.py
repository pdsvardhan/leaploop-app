"""LeapLoop cockpit API (FastAPI). Single-user, behind Authentik forward-auth at the proxy.

Serves the React build + a small REST surface over the engine + shared SQLite. Mutations are
deterministic; tailoring (engine.tailor + engine.pdf) runs as a background task so the UI stays snappy.
"""
from __future__ import annotations
import os, time
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import db, config, settings_store, gmail_confirm
from . import service

REPO = Path(__file__).resolve().parents[2]
WEB_DIST = Path(os.environ.get("LEAPLOOP_WEB_DIST", REPO / "cockpit" / "web" / "dist"))

# Error tracking: dormant until a GlitchTip/Sentry DSN is provided (GlitchTip server deferred to
# Stage 5). Until then, unhandled errors still surface in container logs. Honest mitigation of the
# `no-error-tracking` risk without standing up a full GlitchTip stack for a single-user tool.
_DSN = os.environ.get("GLITCHTIP_DSN") or os.environ.get("SENTRY_DSN")
if _DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=_DSN, traces_sample_rate=0.0)
    except Exception:
        pass

app = FastAPI(title="LeapLoop Cockpit", version="2.0")


def con():
    return db.init_db()


# ----------------------------------------------------------------- models
class Decision(BaseModel):
    decision: str            # yes | no | snooze | reset | mute


class BulkDecision(BaseModel):
    ids: list[str]
    decision: str            # no | snooze | mute | reset  ('yes' is deliberately excluded)


class MasterReviewed(BaseModel):
    note: str = ""


class Applied(BaseModel):
    applied: bool = True


class TailorReq(BaseModel):
    variant: str | None = None


class GenerateReq(BaseModel):
    text: str | None = None
    url: str | None = None
    company: str | None = None
    title: str | None = None


class LogAppliedReq(BaseModel):
    company: str | None = None
    title: str | None = None


class RecompileReq(BaseModel):
    mode: str = "chips"                 # 'chips' (flex fields) | 'tex' (raw LaTeX)
    overrides: dict | None = None       # chip-editor flex fields
    tex: str | None = None              # raw LaTeX (mode='tex')


# ----------------------------------------------------------------- identity
@app.get("/api/me")
def me(request: Request):
    h = request.headers
    name = h.get("x-authentik-name") or h.get("x-forwarded-user") or "Sai Vardhan Palli"
    emailaddr = h.get("x-authentik-email") or "pdsvardhan7@gmail.com"
    initials = "".join(p[0] for p in name.split()[:2]).upper() or "SP"
    return {"name": name, "email": emailaddr, "initials": initials}


# ----------------------------------------------------------------- health
@app.get("/api/health")
def health():
    return service.health_payload(con())


# ----------------------------------------------------------------- roles
@app.get("/api/roles")
def roles(queue: str = "triage"):
    c = con()
    if queue == "tracker":
        rows = service.tracker_rows(c)
        return {"queue": queue, "rows": rows, "count": len(rows)}
    items = service.list_queue(c, queue)
    counts = {
        "triage": c.execute(
            "SELECT count(*) FROM roles WHERE state='triage' OR (state='snoozed' AND COALESCE(snoozed_until,0) <= ?)",
            (time.time(),)).fetchone()[0],
        "apply": c.execute("SELECT count(*) FROM roles WHERE state='picked' AND applied=0").fetchone()[0],
        "applied": c.execute("SELECT count(*) FROM roles WHERE applied=1").fetchone()[0],
    }
    if queue == "triage":
        counts["triage_total"] = counts["triage"]
        counts["triage"] = len(items)        # capped (per-company) — matches what's shown
    return {"queue": queue, "roles": items, "counts": counts}


@app.get("/api/roles/{source_id:path}/jd")
def role_jd(source_id: str):
    c = con()
    r = c.execute("SELECT * FROM roles WHERE source_id=?", (source_id,)).fetchone()
    if not r:
        raise HTTPException(404, "role not found")
    r = dict(r)
    scored = r.get("fit_hint") is not None
    return {"id": r["source_id"], "co": r["company"], "role": r["title"],
            "jd_text": r.get("jd_text") or "", "gaps": [g for g in (r.get("gaps") or "").split(",") if g],
            "fit": int(r["fit_hint"]) if scored else None, "scored": scored,
            "url": r.get("url") or "", "tier": r.get("tier") or "U"}


# Registered before the {source_id:path} routes so the literal path always wins.
@app.post("/api/roles/bulk-decision")
def bulk_decision(body: BulkDecision):
    """Clear the Triage queue in bulk.

    'yes' is intentionally NOT bulk-able: picking triggers a tailor+compile per role and is the
    one act that should stay deliberate (must_have: human footprint = pick + apply only).
    """
    c = con()
    ids = [i for i in (body.ids or []) if i]
    if not ids:
        raise HTTPException(400, "ids must be a non-empty list")
    d = body.decision
    if d == "no":
        n = db.bulk_set_state(c, ids, "skipped")
    elif d == "reset":
        n = db.bulk_set_state(c, ids, "triage")
    elif d == "snooze":
        for sid in ids:
            db.snooze(c, sid, config.SNOOZE_HOURS)
        n = len(ids)
    elif d == "mute":
        companies, n = set(), 0
        for sid in ids:
            r = c.execute("SELECT company FROM roles WHERE source_id=?", (sid,)).fetchone()
            if r and r["company"]:
                companies.add(r["company"])
        for co in companies:
            settings_store.mute_company(c, co)
            n += db.set_company_state(c, co, "muted", ("triage", "snoozed"))
    else:
        raise HTTPException(400, "decision must be no|snooze|reset|mute")
    return {"ok": True, "decision": d, "requested": len(ids), "changed": n}


@app.post("/api/roles/{source_id:path}/decision")
def decide(source_id: str, body: Decision, bg: BackgroundTasks):
    c = con()
    r = c.execute("SELECT * FROM roles WHERE source_id=?", (source_id,)).fetchone()
    if not r:
        raise HTTPException(404, "role not found")
    d = body.decision
    if d == "yes":
        db.set_state(c, source_id, "picked")
        bg.add_task(service.tailor_role, source_id)      # tailor + compile in the background
    elif d == "no":
        db.set_state(c, source_id, "skipped")
    elif d == "snooze":
        db.snooze(c, source_id, config.SNOOZE_HOURS)
    elif d == "reset":                                    # undo -> back to Triage
        db.set_state(c, source_id, "triage")
    elif d == "mute":
        co = dict(r)["company"]
        settings_store.mute_company(c, co)
        db.set_company_state(c, co, "muted", ("triage", "snoozed"))   # reversible via unmute
    else:
        raise HTTPException(400, "decision must be yes|no|snooze|reset|mute")
    return {"ok": True, "decision": d, "id": source_id}


@app.post("/api/roles/{source_id:path}/tailor")
def tailor_now(source_id: str, body: TailorReq):
    res = service.tailor_role(source_id, force_variant=body.variant)   # synchronous (swap variant)
    if not res:
        raise HTTPException(404, "role not found")
    return {"ok": True, **res}


@app.get("/api/roles/{source_id:path}/edit")
def role_edit(source_id: str):
    res = service.role_edit_state(source_id)
    if not res:
        raise HTTPException(404, "role not found")
    return res


@app.post("/api/roles/{source_id:path}/recompile")
def role_recompile(source_id: str, body: RecompileReq):
    res = service.recompile_role(source_id, mode=body.mode, overrides=body.overrides, tex=body.tex)
    if res is None:
        raise HTTPException(404, "role not found")
    if not res.get("ok"):
        return JSONResponse(status_code=422, content=res)
    return res


@app.post("/api/roles/{source_id:path}/applied")
def set_applied(source_id: str, body: Applied):
    c = con()
    row = db.mark_applied(c, source_id, body.applied)
    if not row:
        raise HTTPException(404, "role not found")
    if body.applied:
        rr = dict(row)
        db.add_applied(c, rr["company"], rr["title"], resume=rr.get("pdf_path") or "", source="manual")
    return {"ok": True, "applied": body.applied, "id": source_id}


# ----------------------------------------------------------------- manual generate
@app.post("/api/generate")
def generate(body: GenerateReq):
    res = service.generate_pdf(text=body.text or "", url=body.url or "",
                               company=body.company or "", title=body.title or "")
    if not res.get("ok"):
        return JSONResponse(status_code=422, content=res)
    res["pdf_url"] = f"/api/pdf/generated/{res['token']}"
    return res


@app.post("/api/generate/{token}/applied")
def generate_applied(token: str, body: LogAppliedReq):
    """Log a manually generated CV as applied so the role stops resurfacing in Triage."""
    res = service.log_generated_applied(token, company=body.company or "", title=body.title or "")
    if not res.get("ok"):
        return JSONResponse(status_code=422, content=res)
    return res


@app.delete("/api/generate/{token}/applied")
def generate_unapplied(token: str):
    """Undo the applied log for a generated résumé (mis-click recovery)."""
    res = service.unlog_generated_applied(token)
    if not res.get("ok"):
        return JSONResponse(status_code=422, content=res)
    return res


@app.get("/api/generate/{token}/edit")
def generate_edit(token: str):
    res = service.generated_edit_state(token)
    if not res:
        raise HTTPException(404, "generated résumé not found (regenerate it)")
    return res


@app.post("/api/generate/{token}/recompile")
def generate_recompile(token: str, body: RecompileReq):
    res = service.recompile_generated(token, mode=body.mode, overrides=body.overrides, tex=body.tex)
    if not res.get("ok"):
        return JSONResponse(status_code=422, content=res)
    return res


# ----------------------------------------------------------------- settings
@app.get("/api/settings")
def get_settings():
    return settings_store.get_settings(con())


@app.put("/api/settings")
async def put_settings(request: Request):
    patch = await request.json()
    return settings_store.put_settings(con(), patch if isinstance(patch, dict) else {})


@app.post("/api/companies/unmute")
async def unmute_company(request: Request):
    body = await request.json()
    co = (body or {}).get("company", "")
    if not co:
        raise HTTPException(400, "company required")
    c = con()
    settings_store.unmute_company(c, co)
    restored = db.set_company_state(c, co, "triage", ("muted",))   # bring its roles back to Triage
    return {"ok": True, "company": co, "restored": restored}


@app.get("/api/integrations")
def integrations():
    return service.integration_status(con())


# ----------------------------------------------------------------- résumé freshness (item 888)
@app.get("/api/resume/status")
def resume_status():
    """Freshness of the résumé master: open-ended roles + when you last confirmed it."""
    c = con()
    return {**service.master_review_state(c),
            "openEnded": service._open_ended_entries(),
            "warnings": service.resume_warnings(c)}


@app.post("/api/resume/reviewed")
def resume_reviewed(body: MasterReviewed):
    """Confirm the master is current — clears the open-ended-role warning for the interval."""
    return {"ok": True, **service.mark_master_reviewed(con(), body.note)}


# ----------------------------------------------------------------- pdf serving
def _send_pdf(path_str: str | None, company: str = ""):
    p = service.resolve_pdf(path_str) if path_str else None
    if not p:
        raise HTTPException(404, "no PDF yet")
    # adr-011: the served name carries the company so two downloads in one sitting do not
    # collide in ~/Downloads and reach the recruiter as "... CV (1).pdf".
    name = service.download_filename(company)
    return FileResponse(p, media_type="application/pdf", filename=name,
                        headers={"Content-Disposition": f'inline; filename="{name}"'})


@app.get("/api/pdf/generated/{token}")
def pdf_generated(token: str):
    return _send_pdf(str(service.pdf_dir_for(f"_generated/{token}", create=False)
                         / config.PDF_OUTPUT_NAME),
                     service.generated_company(token))


@app.get("/api/resume/master")
def resume_master():
    """The clean default/master résumé (no JD tailoring) — the in-hand one-pager."""
    try:
        return _send_pdf(str(service.master_resume_pdf()))
    except Exception as e:
        raise HTTPException(500, f"resume compile failed: {str(e)[:120]}")


@app.get("/api/pdf/{source_id:path}")
def pdf_role(source_id: str):
    r = con().execute("SELECT pdf_path, company FROM roles WHERE source_id=?",
                      (source_id,)).fetchone()
    if not r:
        raise HTTPException(404, "role not found")
    r = dict(r)
    return _send_pdf(r["pdf_path"], r.get("company") or "")


# ----------------------------------------------------------------- maintenance
@app.post("/api/sync")
def sync():
    """On-demand Gmail auto-confirm pass (the cron does this every cycle too)."""
    try:
        return {"ok": True, **gmail_confirm.sync_applied(con())}
    except Exception as e:
        return JSONResponse(status_code=502, content={"ok": False, "error": str(e)[:200]})


@app.get("/api/healthz")
def healthz():
    try:
        con().execute("SELECT 1")
        return {"status": "ok", "db": "connected", "version": app.version}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "error": str(e)[:200]})


# ----------------------------------------------------------------- static SPA
if (WEB_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")


@app.get("/")
def index():
    idx = WEB_DIST / "index.html"
    return FileResponse(idx) if idx.exists() else JSONResponse({"status": "api-only", "web": "not built"})


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "not found")
    idx = WEB_DIST / "index.html"
    if idx.exists():
        return FileResponse(idx)
    raise HTTPException(404, "web build missing")
