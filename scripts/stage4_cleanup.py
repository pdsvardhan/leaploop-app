"""Stage-4 one-off: unmute Amazon + restore its roles to Triage (the old mute parked them in
'skipped'), re-skip roles explicitly requiring >6 yrs, then a fresh cycle. The per-company cap
(6) keeps Amazon from flooding the queue."""
from engine import db, settings_store, cleaner, config, run
import collections

con = db.init_db()
settings_store.unmute_company(con, "Amazon")
restored = db.set_company_state(con, "Amazon", "triage", ("skipped", "muted"))
print("Amazon unmuted; roles restored to triage:", restored, "| muted now:", settings_store.get_settings(con).get("muted"))

cap = config.MAX_YEARS_EXPERIENCE
skipped = 0
for r in con.execute("SELECT source_id, jd_text FROM roles WHERE state IN ('triage','snoozed')").fetchall():
    req = cleaner.min_years_required(r["jd_text"] or "")
    if req is not None and req > cap:
        db.set_state(con, r["source_id"], "skipped")
        skipped += 1
print(f"re-skipped explicit >{cap}yr roles:", skipped)

print("running fresh cycle...")
print(run.cycle())
print("states:", dict(collections.Counter(x[0] for x in con.execute("SELECT state FROM roles"))))
print("triage by company (top):",
      con.execute("SELECT company, count(*) c FROM roles WHERE state IN ('triage','snoozed') GROUP BY company ORDER BY c DESC LIMIT 6").fetchall())
