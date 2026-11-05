"""One poll cycle: fetch -> clean -> tier -> store new -> auto-confirm applied.
The cron entry point. Every external step is alert-and-skip: one bad source never aborts a cycle."""
from __future__ import annotations
import time
try:
    from . import db, watcher, cleaner, tailor, gmail_confirm, settings_store
except ImportError:
    import db, watcher, cleaner, tailor, gmail_confirm, settings_store


def _gmail_leg(con, linkedin: bool, confirm: bool) -> tuple[list, int, dict]:
    """Both Gmail-IMAP legs over ONE shared connection.

    Previously each leg opened its own connection and fetched one message at a time, which is
    what Gmail throttled into "System Error" / socket EOF. Every attempt is recorded to
    integration_health so a failure is visible in the cockpit, not just in watcher.log.
    """
    li_roles: list = []
    confirmed = 0
    status = {"linkedin-ingest": None, "gmail-confirm": None}
    if not (linkedin or confirm):
        return li_roles, confirmed, status

    m = None
    try:
        # A Session, not a bare connection: if Gmail drops the socket mid-cycle it reconnects
        # once instead of retrying a dead one three times (iter-170).
        m = gmail_confirm.Session()
    except Exception as e:
        err = str(e)[:200]
        print(f"  gmail connect failed: {err}")
        for leg, wanted in (("linkedin-ingest", linkedin), ("gmail-confirm", confirm)):
            if wanted:
                db.record_integration(con, leg, False, err)
                status[leg] = "FAIL"
        return li_roles, confirmed, status

    try:
        if linkedin:
            try:
                li_roles = gmail_confirm.ingest_linkedin(m=m)
                db.record_integration(con, "linkedin-ingest", True)
                status["linkedin-ingest"] = "ok"
            except Exception as e:
                print(f"  linkedin-ingest skipped: {str(e)[:120]}")
                db.record_integration(con, "linkedin-ingest", False, str(e))
                status["linkedin-ingest"] = "FAIL"
        if confirm:
            try:
                confirmed = gmail_confirm.sync_applied(con, m=m).get("flipped", 0)
                db.record_integration(con, "gmail-confirm", True)
                status["gmail-confirm"] = "ok"
            except Exception as e:
                print(f"  gmail-confirm skipped: {str(e)[:120]}")
                db.record_integration(con, "gmail-confirm", False, str(e))
                status["gmail-confirm"] = "FAIL"
    finally:
        gmail_confirm.close_quietly(m)
    return li_roles, confirmed, status


def cycle(linkedin: bool = True, confirm: bool = True) -> dict:
    con = db.init_db()
    raw, health = watcher.poll()
    db.record_health(con, health)

    li_roles, confirmed, gmail_status = _gmail_leg(con, linkedin, confirm)
    raw += li_roles
    li = len(li_roles)

    rules = tailor.load_rules()
    cleaned = cleaner.clean(raw, con=con)
    new = 0
    for r in cleaned:
        jd = (r.get("jd_text") or "").strip()
        if jd:
            rt = r.get("title") or ""
            _, hits = tailor.choose_cluster(jd, rules, title=rt)
            r["fit_hint"] = len(hits)
            r["gaps"] = ",".join(tailor.detect_gaps(jd, rules, title=rt).keys())
        else:
            # No JD -> nothing was scored. NULL says "not scored"; 0 would have claimed
            # "scored, matched nothing", which is the false signal item 886 removes.
            r["fit_hint"] = None
            r["gaps"] = ""
        if db.upsert_role(con, r):
            new += 1

    aged = db.age_out_triage(con, settings_store.effective_age_out_days(con))

    healthy = sum(1 for h in health.values() if h["ok"])
    summary = {"fetched": len(raw), "linkedin": li, "kept": len(cleaned), "new": new,
               "confirmed": confirmed, "aged_out": aged, "feeds_ok": f"{healthy}/{len(health)}"}
    # Surface a broken integration in the cycle line itself. The old summary printed a healthy
    # feeds_ok=18/18 while Gmail had been dead for weeks.
    broken = [k for k, v in gmail_status.items() if v == "FAIL"]
    if broken:
        summary["gmail"] = "FAIL:" + ",".join(broken)
    print(f"[{time.strftime('%Y-%m-%d %H:%M')}] " +
          " ".join(f"{k}={v}" for k, v in summary.items()))
    return summary


if __name__ == "__main__":
    cycle()
