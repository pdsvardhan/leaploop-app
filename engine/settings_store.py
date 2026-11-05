"""Persisted, editable cockpit settings (filters + watch-list).

Defaults come from config.py; user edits live in the `settings` table so a change made in the
Settings screen takes effect on the *next* poll. The locked India-PM band stays config-driven
(a must-have); what the user tunes here is the exclude list and the watch-list tiers.
"""
from __future__ import annotations
import json, time

try:
    from . import config, db
except ImportError:
    import config, db

_KEY = "cockpit"


def _defaults() -> dict:
    wl = ([{"co": c, "tier": "A"} for c in config.TIER_A]
          + [{"co": c, "tier": "B"} for c in config.TIER_B]
          + [{"co": c, "tier": "C"} for c in getattr(config, "TIER_C", [])])
    return {
        "filters": {
            "roleTypes": ["Product Manager", "Senior Product Manager", "Associate Product Manager",
                          "Platform PM", "Technical PM", "Growth PM", "AI PM"],
            "levels": ["APM", "PM", "PM I", "PM II", "Senior PM"],
            "activeLevels": ["APM", "PM", "PM I", "PM II", "Senior PM"],
            "exclude": list(config.EXCLUDE_KEYWORDS),
            "locations": ["Bengaluru", "Mumbai", "Gurugram", "Hyderabad", "Delhi NCR",
                          "Pune", "Chennai", "Remote, India"],
        },
        "watchlist": wl,
        "muted": [],
        "country": config.COUNTRY_ONLY,
        # Triage roles older than this are auto-skipped so the queue stays a decision surface
        # rather than a landfill (iter-141, item 889). 0 disables age-out.
        "ageOutDays": 30,
        # Append the company to the DOWNLOADED résumé filename (adr-011). The file on disk
        # keeps its constant name; this only changes what the browser saves it as.
        "nameWithCompany": True,
    }


def get_settings(con) -> dict:
    base = _defaults()
    row = con.execute("SELECT value FROM settings WHERE key=?", (_KEY,)).fetchone()
    if row:
        try:
            stored = json.loads(row[0])
            if isinstance(stored.get("filters"), dict):
                base["filters"].update(stored["filters"])
            if isinstance(stored.get("watchlist"), list):
                base["watchlist"] = stored["watchlist"]
            if isinstance(stored.get("muted"), list):
                base["muted"] = stored["muted"]
            if isinstance(stored.get("ageOutDays"), (int, float)):
                base["ageOutDays"] = int(stored["ageOutDays"])
            if isinstance(stored.get("nameWithCompany"), bool):
                base["nameWithCompany"] = stored["nameWithCompany"]
        except Exception:
            pass
    return base


def put_settings(con, patch: dict) -> dict:
    cur = get_settings(con)
    if isinstance(patch.get("filters"), dict):
        cur["filters"].update(patch["filters"])
    if isinstance(patch.get("watchlist"), list):
        cur["watchlist"] = patch["watchlist"]
    if isinstance(patch.get("muted"), list):
        cur["muted"] = patch["muted"]
    if isinstance(patch.get("ageOutDays"), (int, float)):
        cur["ageOutDays"] = max(0, int(patch["ageOutDays"]))
    if isinstance(patch.get("nameWithCompany"), bool):
        cur["nameWithCompany"] = patch["nameWithCompany"]
    con.execute("INSERT OR REPLACE INTO settings(key,value,updated) VALUES(?,?,?)",
                (_KEY, json.dumps(cur), time.time()))
    con.commit()
    return cur


def effective_excludes(con) -> list[str]:
    """Cleaner's exclude list = config defaults plus any user additions (lower-cased, deduped)."""
    s = get_settings(con)
    user = [w.lower() for w in s["filters"].get("exclude", []) if w]
    return sorted(set(w.lower() for w in config.EXCLUDE_KEYWORDS) | set(user))


def effective_curated(con) -> dict:
    """Watch-list tier pins {company_lower: tier} — let the user re-tier a company from Settings."""
    s = get_settings(con)
    return {w["co"].lower(): w["tier"] for w in s.get("watchlist", []) if w.get("co") and w.get("tier")}


def effective_age_out_days(con) -> int:
    """How stale a Triage role may get before the cycle auto-skips it. 0 = never."""
    try:
        return max(0, int(get_settings(con).get("ageOutDays", 30)))
    except (TypeError, ValueError):
        return 30


def effective_muted(con) -> set[str]:
    """Normalized company names the user muted — dropped before they reach Triage."""
    s = get_settings(con)
    return {db.norm(c) for c in s.get("muted", []) if c}


def mute_company(con, company: str) -> dict:
    s = get_settings(con)
    muted = [m for m in s.get("muted", []) if m]
    if company and company not in muted:
        muted.append(company)
    return put_settings(con, {"muted": muted})


def unmute_company(con, company: str) -> dict:
    s = get_settings(con)
    low = (company or "").strip().lower()
    muted = [m for m in s.get("muted", []) if m and m.strip().lower() != low]
    return put_settings(con, {"muted": muted})


def set_status(con, key: str, value: dict) -> None:
    """Persist a small runtime/integration status blob (e.g. last Telegram push outcome)."""
    con.execute("INSERT OR REPLACE INTO settings(key,value,updated) VALUES(?,?,?)",
                (f"status:{key}", json.dumps(value), time.time()))
    con.commit()


def get_status(con, key: str):
    row = con.execute("SELECT value FROM settings WHERE key=?", (f"status:{key}",)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None
