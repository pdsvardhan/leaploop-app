"""SQLite store for LeapLoop. One roles table (state machine) + applied index + feed health."""
from __future__ import annotations
import os, sqlite3, time
from pathlib import Path

DB_PATH = Path(os.environ.get("LEAPLOOP_DB", Path(__file__).resolve().parent.parent / "data" / "leaploop.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
  source_id   TEXT PRIMARY KEY,
  company     TEXT NOT NULL,
  title       TEXT NOT NULL,
  location    TEXT,
  mode        TEXT,
  source      TEXT,            -- ATS | LinkedIn
  url         TEXT,
  jd_text     TEXT,
  posted      TEXT,
  tier        TEXT,            -- A | B | C | U
  fit_hint    INTEGER DEFAULT 0,
  gaps        TEXT,            -- comma list of honest-gap keys triggered
  state       TEXT DEFAULT 'triage',   -- triage | snoozed | picked | skipped | applied
  variant     TEXT,
  overrides_json TEXT,        -- last chip-editor override dict, raw JSON (round-trips the editor)
  pdf_path    TEXT,
  applied     INTEGER DEFAULT 0,
  applied_at  TEXT,
  snoozed_until REAL,
  first_seen  REAL,
  updated     REAL
);
CREATE TABLE IF NOT EXISTS applied_index (
  company_norm TEXT, title_norm TEXT, resume TEXT, source TEXT, date TEXT,
  PRIMARY KEY (company_norm, title_norm)
);
CREATE TABLE IF NOT EXISTS feed_health (
  company TEXT PRIMARY KEY, ok INTEGER, count INTEGER, err TEXT, last REAL
);
CREATE TABLE IF NOT EXISTS company_tier (
  name TEXT PRIMARY KEY, tier TEXT, decided_at REAL, via TEXT
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY, value TEXT, updated REAL
);
CREATE TABLE IF NOT EXISTS integration_health (
  name TEXT PRIMARY KEY,   -- gmail-confirm | linkedin-ingest
  ok INTEGER,              -- outcome of the LAST attempt
  last_attempt REAL,
  last_success REAL,       -- NULL until it has ever worked
  last_error TEXT
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db(con=None):
    c = con or connect()
    c.executescript(SCHEMA)
    _migrate(c)
    c.commit()
    return c


def _migrate(c):
    """Idempotent column adds for DBs created before a column existed."""
    cols = {r[1] for r in c.execute("PRAGMA table_info(roles)")}
    if "snoozed_until" not in cols:
        c.execute("ALTER TABLE roles ADD COLUMN snoozed_until REAL")
    # iter-170: the chip editor had nowhere to persist its values, so a second edit reseeded
    # from the default cluster and silently dropped the first edit.
    if "overrides_json" not in cols:
        c.execute("ALTER TABLE roles ADD COLUMN overrides_json TEXT")
    # iter-141 item 886: JD-less roles were stored with fit_hint=0, which the UI rendered as a
    # real score of zero. NULL is the honest value — "never scored, there was no JD".
    c.execute("UPDATE roles SET fit_hint=NULL "
              "WHERE fit_hint=0 AND (jd_text IS NULL OR TRIM(jd_text)='')")


def upsert_role(con, role: dict) -> bool:
    """Insert if new (by source_id). Returns True if it was NEW."""
    now = time.time()
    cur = con.execute("SELECT 1 FROM roles WHERE source_id=?", (role["source_id"],))
    if cur.fetchone():
        return False
    con.execute(
        """INSERT INTO roles (source_id,company,title,location,mode,source,url,jd_text,posted,
             tier,fit_hint,gaps,state,first_seen,updated)
           VALUES (:source_id,:company,:title,:location,:mode,:source,:url,:jd_text,:posted,
             :tier,:fit_hint,:gaps,'triage',:now,:now)""",
        {**{k: role.get(k) for k in
            ("source_id", "company", "title", "location", "mode", "source", "url", "jd_text",
             "posted", "tier", "fit_hint", "gaps")}, "now": now},
    )
    con.commit()
    return True


def set_state(con, source_id, state):
    con.execute("UPDATE roles SET state=?, updated=? WHERE source_id=?", (state, time.time(), source_id))
    con.commit()


def snooze(con, source_id, hours=12):
    """Snooze a role: hide it from Triage for `hours`, then it resurfaces (state stays 'snoozed')."""
    now = time.time()
    con.execute("UPDATE roles SET state='snoozed', snoozed_until=?, updated=? WHERE source_id=?",
                (now + hours * 3600, now, source_id))
    con.commit()


def set_company_state(con, company, to_state, from_states):
    """Move all of a company's roles in `from_states` to `to_state` (normalized company match).
    Used by mute (-> 'muted') and unmute (-> 'triage') so a mute is cleanly reversible."""
    cn = norm(company)
    fs, n, now = set(from_states), 0, time.time()
    for r in con.execute("SELECT source_id, company, state FROM roles").fetchall():
        if r["state"] in fs and norm(r["company"]) == cn:
            con.execute("UPDATE roles SET state=?, updated=? WHERE source_id=?", (to_state, now, r["source_id"]))
            n += 1
    con.commit()
    return n


def mark_applied(con, source_id, applied=True, resume=""):
    """Flip one role's applied flag. applied=True -> state 'applied' + timestamp; False undoes it."""
    now = time.time()
    if applied:
        con.execute(
            "UPDATE roles SET applied=1, state='applied', applied_at=?, updated=? WHERE source_id=?",
            (time.strftime("%Y-%m-%d %H:%M"), now, source_id),
        )
    else:
        con.execute(
            "UPDATE roles SET applied=0, state='picked', applied_at=NULL, updated=? WHERE source_id=?",
            (now, source_id),
        )
    con.commit()
    return con.execute("SELECT * FROM roles WHERE source_id=?", (source_id,)).fetchone()


def find_active_by_company(con, company, states=("picked",)):
    """Roles for a company in the given states, not yet applied, newest first.

    Default scope is 'picked' only: auto-confirm should mark a role applied that the user
    actually said yes to — never a fresh Triage role that merely shares a company with an
    old confirmation email. Matches on normalized company so "CRED" finds "Cred".
    """
    want = norm(company)
    if not want:
        return []
    rows = con.execute("SELECT * FROM roles WHERE applied=0 ORDER BY updated DESC").fetchall()
    want_states = set(states)
    out = []
    for r in rows:
        if r["state"] not in want_states:
            continue
        have = norm(r["company"])
        if have and (have == want or want in have or have in want):
            out.append(dict(r))
    return out


def get_by_state(con, state):
    return [dict(r) for r in con.execute("SELECT * FROM roles WHERE state=? ORDER BY first_seen DESC", (state,))]


def all_role_idents(con):
    """(source_id, company, title) for every stored role — used by the cleaner's repost dedup."""
    return [(r["source_id"], r["company"], r["title"])
            for r in con.execute("SELECT source_id, company, title FROM roles")]


def norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum() or ch == " ").strip()


def already_applied(con, company, title) -> bool:
    r = con.execute("SELECT 1 FROM applied_index WHERE company_norm=? AND title_norm=?",
                    (norm(company), norm(title))).fetchone()
    return r is not None


def add_applied(con, company, title, resume="", source="", date=""):
    con.execute("INSERT OR REPLACE INTO applied_index VALUES (?,?,?,?,?)",
                (norm(company), norm(title), resume, source, date or time.strftime("%Y-%m-%d")))
    con.commit()


def get_applied(con, company, title) -> dict | None:
    """The applied_index row for this company+title, or None. Used to decide ownership from
    what the row holds NOW rather than from what a caller remembers writing."""
    r = con.execute("SELECT * FROM applied_index WHERE company_norm=? AND title_norm=?",
                    (norm(company), norm(title))).fetchone()
    return dict(r) if r else None


def remove_applied(con, company, title) -> int:
    """Undo an applied_index row. A mis-click on "Log as applied" otherwise left a permanent
    row claiming an application that never happened, with no way to take it back."""
    cur = con.execute("DELETE FROM applied_index WHERE company_norm=? AND title_norm=?",
                      (norm(company), norm(title)))
    con.commit()
    return cur.rowcount or 0


def record_health(con, health: dict):
    for co, h in health.items():
        con.execute("INSERT OR REPLACE INTO feed_health VALUES (?,?,?,?,?)",
                    (co, 1 if h["ok"] else 0, h["count"], h.get("err"), h["last"]))
    con.commit()


def record_integration(con, name: str, ok: bool, err: str | None = None):
    """Record the outcome of one integration attempt.

    last_success is preserved across failures — the gap between last_success and now is what
    tells you an integration has quietly stopped working. Before this, a Gmail failure existed
    only as a line in watcher.log and /api/integrations still reported 'configured: true'.
    """
    now = time.time()
    prev = con.execute("SELECT last_success FROM integration_health WHERE name=?", (name,)).fetchone()
    last_success = now if ok else (prev["last_success"] if prev else None)
    con.execute("INSERT OR REPLACE INTO integration_health VALUES (?,?,?,?,?)",
                (name, 1 if ok else 0, now, last_success, None if ok else _clean_err(err)))
    con.commit()


def _clean_err(err) -> str:
    """imaplib raises with the raw server bytes, so str(e) is a b'...' repr — which reached
    the Settings screen verbatim as b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'."""
    s = str(err or "").strip()
    if len(s) > 2 and s[0] == "b" and s[1] in "'\"" and s[-1] == s[1]:
        s = s[2:-1]
    return s.replace("\\r\\n", " ").replace("\\n", " ").strip()[:400]


def get_integrations(con) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM integration_health ORDER BY name")]


def bulk_set_state(con, source_ids: list[str], state: str) -> int:
    """Move many roles to a state in one transaction (Triage bulk decide).

    Returns the TOTAL rows changed. `SELECT changes()` after an executemany reports only the
    LAST statement's count — it returned 1 for a 30-role discard, and 0 when the last id was
    already decided, so the UI said "Discarded 0 roles" while 29 were discarded. cursor.rowcount
    accumulates across an executemany, which is the number the toast needs.
    """
    if not source_ids:
        return 0
    now = time.time()
    cur = con.executemany("UPDATE roles SET state=?, updated=? WHERE source_id=?",
                          [(state, now, sid) for sid in source_ids])
    con.commit()
    return max(0, cur.rowcount)


def age_out_triage(con, days: int) -> int:
    """Auto-skip triage roles first seen more than `days` ago.

    Keeps the queue a decision surface instead of a landfill. Only touches 'triage' and
    'snoozed' — never a role the owner already picked, skipped, muted or applied.
    """
    if not days or days <= 0:
        return 0
    cutoff = time.time() - days * 86400
    cur = con.execute(
        "UPDATE roles SET state='skipped', updated=? "
        "WHERE state IN ('triage','snoozed') AND COALESCE(first_seen,0) < ? AND applied=0",
        (time.time(), cutoff))
    con.commit()
    return cur.rowcount or 0


def cache_tier(con, name, tier, via):
    con.execute("INSERT OR REPLACE INTO company_tier VALUES (?,?,?,?)", (name, tier, time.time(), via))
    con.commit()


def get_cached_tier(con, name):
    r = con.execute("SELECT tier FROM company_tier WHERE name=?", (name,)).fetchone()
    return r["tier"] if r else None
