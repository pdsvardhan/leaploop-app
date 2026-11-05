"""One-time import of the genuinely-applied rows from APPLICATIONS_TRACKER.xlsx into applied_index.

Idempotent (PK = company_norm + title_norm; INSERT OR REPLACE). Backs the DB up first.
Source: cockpit/api/applied_seed.json (extracted from the xlsx; only Status='Applied*' rows).
Run on the server:  .venv/bin/python -m scripts.import_applied
"""
from __future__ import annotations
import json, shutil, time
from pathlib import Path

from engine import db

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "cockpit" / "api" / "applied_seed.json"


def main():
    con = db.init_db()
    before = con.execute("SELECT count(*) FROM applied_index").fetchone()[0]
    bak = db.DB_PATH.with_suffix(f".db.bak-import-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copyfile(db.DB_PATH, bak)
    print(f"backup: {bak.name}  (applied_index before: {before})")

    rows = json.loads(SEED.read_text(encoding="utf-8"))
    for r in rows:
        db.add_applied(con, r["company"], r["title"],
                       resume=r.get("resume") or "", source=r.get("source") or "tracker-import",
                       date=r.get("date") or "")
    after = con.execute("SELECT count(*) FROM applied_index").fetchone()[0]
    print(f"imported {len(rows)} applied rows -> applied_index now {after} (+{after - before})")


if __name__ == "__main__":
    main()
