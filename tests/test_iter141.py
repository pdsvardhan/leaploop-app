"""Tests for iteration 141 — the fixes AND the two defects the verifier caught.

Every test here maps to a locked item; the ones marked REGRESSION encode a bug that actually
shipped and was caught at the verifier gate, so it cannot come back silently.
Run: `pytest -q` from the repo root.
"""
import sqlite3
import time

import pytest

from engine import db, gmail_confirm, settings_store
from cockpit.api import service


def _mem_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    db.init_db(con)
    return con


def _role(con, sid, *, company="Cred", title="Product Manager", state="triage",
          source="ATS", jd="", age_days=0.0, fit=None):
    db.upsert_role(con, {"source_id": sid, "company": company, "title": title,
                         "location": "India", "source": source, "tier": "A",
                         "jd_text": jd, "fit_hint": fit})
    con.execute("UPDATE roles SET state=?, first_seen=? WHERE source_id=?",
                (state, time.time() - age_days * 86400, sid))
    con.commit()


# ------------------------------------------------------- item 889: bulk decide
def test_bulk_set_state_reports_total_rows_changed():
    """REGRESSION: `SELECT changes()` after executemany returned only the LAST statement's
    count, so discarding 30 roles toasted "Discarded 1 role"."""
    con = _mem_db()
    ids = [f"gh:c:{i}" for i in range(5)]
    for sid in ids:
        _role(con, sid)
    assert db.bulk_set_state(con, ids, "skipped") == 5
    assert con.execute("SELECT COUNT(*) FROM roles WHERE state='skipped'").fetchone()[0] == 5


def test_bulk_set_state_count_correct_when_last_id_is_stale():
    """REGRESSION: with a non-existent id LAST in the list, changes() returned 0 — the UI said
    "Discarded 0 roles" while the rest really were discarded, inviting a destructive retry."""
    con = _mem_db()
    real = [f"gh:d:{i}" for i in range(3)]
    for sid in real:
        _role(con, sid)
    changed = db.bulk_set_state(con, real + ["gh:does-not-exist"], "skipped")
    assert changed == 3, f"expected 3 real rows changed, got {changed}"


def test_bulk_set_state_empty_is_noop():
    assert db.bulk_set_state(_mem_db(), [], "skipped") == 0


# ------------------------------------------------------- item 889: age-out
def test_age_out_only_touches_stale_triage_and_snoozed():
    con = _mem_db()
    _role(con, "old:triage", state="triage", age_days=40)
    _role(con, "old:snoozed", state="snoozed", age_days=40)
    _role(con, "new:triage", state="triage", age_days=5)
    _role(con, "old:picked", state="picked", age_days=40)
    _role(con, "old:muted", state="muted", age_days=40)
    _role(con, "old:skipped", state="skipped", age_days=40)

    assert db.age_out_triage(con, 30) == 2

    state = {r["source_id"]: r["state"] for r in con.execute("SELECT source_id, state FROM roles")}
    assert state["old:triage"] == "skipped"
    assert state["old:snoozed"] == "skipped"
    assert state["new:triage"] == "triage"      # inside the window
    assert state["old:picked"] == "picked"      # a decision the owner made — never touched
    assert state["old:muted"] == "muted"
    assert state["old:skipped"] == "skipped"


def test_age_out_never_touches_an_applied_role():
    con = _mem_db()
    _role(con, "old:applied", state="triage", age_days=99)
    db.mark_applied(con, "old:applied", True)
    assert db.age_out_triage(con, 30) == 0
    row = con.execute("SELECT state, applied FROM roles WHERE source_id='old:applied'").fetchone()
    assert row["state"] == "applied" and row["applied"] == 1


@pytest.mark.parametrize("days", [0, -1, None])
def test_age_out_disabled_is_noop(days):
    con = _mem_db()
    _role(con, "ancient", state="triage", age_days=500)
    assert db.age_out_triage(con, days) == 0
    assert con.execute("SELECT state FROM roles WHERE source_id='ancient'").fetchone()[0] == "triage"


def test_age_out_days_setting_roundtrip_and_clamp():
    con = _mem_db()
    assert settings_store.effective_age_out_days(con) == 30           # default
    settings_store.put_settings(con, {"ageOutDays": 7})
    assert settings_store.effective_age_out_days(con) == 7
    settings_store.put_settings(con, {"ageOutDays": -5})              # clamped, never negative
    assert settings_store.effective_age_out_days(con) == 0


# ------------------------------------------------------- item 885: integration health
def test_last_success_survives_a_later_failure():
    con = _mem_db()
    db.record_integration(con, "gmail-confirm", True)
    ok_at = con.execute("SELECT last_success FROM integration_health").fetchone()[0]
    assert ok_at

    db.record_integration(con, "gmail-confirm", False, "FETCH => System Error")
    row = dict(con.execute("SELECT * FROM integration_health").fetchone())
    assert row["ok"] == 0
    assert row["last_success"] == ok_at          # the gap is what reveals a dead integration
    assert "System Error" in row["last_error"]


def test_integration_leg_status_derivation():
    now = time.time()
    assert service._integration_leg("g", False, None)["status"] == "not-configured"
    assert service._integration_leg("g", True, None)["status"] == "unknown"
    assert service._integration_leg("g", True, {"ok": 1, "last_attempt": now,
                                                "last_success": now})["status"] == "ok"
    # failing now but succeeded minutes ago -> degraded
    assert service._integration_leg("g", True, {"ok": 0, "last_attempt": now,
                                                "last_success": now - 600,
                                                "last_error": "x"})["status"] == "degraded"
    # failing and no success for longer than the stale window -> failed
    failed = service._integration_leg("g", True, {"ok": 0, "last_attempt": now,
                                                  "last_success": now - 99999,
                                                  "last_error": "x"})
    assert failed["status"] == "failed" and failed["healthy"] is False


# ------------------------------------------------------- item 884: IMAP batching
class _FakeIMAP:
    """Records what was asked of the server so we can assert ONE batched FETCH."""

    def __init__(self):
        self.fetches = []

    def fetch(self, seq, spec):
        self.fetches.append(seq)
        return "OK", [(b"1 (RFC822 {3}", b"hi"), b")"]


def test_fetch_batch_issues_a_single_round_trip():
    """The N+1 FETCH loop is what Gmail throttled into 'System Error'."""
    m = _FakeIMAP()
    nums = [str(i).encode() for i in range(1, 51)]
    gmail_confirm._fetch_batch(m, nums, "(RFC822)")
    assert len(m.fetches) == 1, f"expected 1 batched FETCH, got {len(m.fetches)}"
    assert m.fetches[0] == ",".join(str(i) for i in range(1, 51))


def test_fetch_batch_empty_makes_no_request():
    m = _FakeIMAP()
    assert gmail_confirm._fetch_batch(m, [], "(RFC822)") == []
    assert m.fetches == []


def test_with_retry_retries_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise gmail_confirm.imaplib.IMAP4.error("System Error")
        return "ok"

    assert gmail_confirm.with_retry(flaky, attempts=3, base_delay=0) == "ok"
    assert calls["n"] == 3


def test_with_retry_reraises_after_exhausting_attempts():
    def always():
        raise OSError("EOF")

    with pytest.raises(OSError):
        gmail_confirm.with_retry(always, attempts=2, base_delay=0)


def test_linkedin_alert_parse_never_invents_a_jd():
    """LinkedIn alerts carry no description; jd_text must stay empty (item 886)."""
    html = ('<a href="https://www.linkedin.com/comm/jobs/view/12345/?x=1">Senior Product Manager</a>'
            'Philips · Bengaluru, India')
    roles = gmail_confirm.parse_linkedin_html(html)
    assert len(roles) == 1
    assert roles[0]["jd_text"] == ""
    assert roles[0]["source"] == "LinkedIn"
    assert roles[0]["source_id"] == "li:12345"


# ------------------------------------------------------- items 886/887: honest cards
def test_role_card_reports_no_score_when_there_is_no_jd():
    card = service.role_card(
        {"source_id": "li:1", "company": "Philips", "title": "PM", "source": "LinkedIn",
         "jd_text": "", "fit_hint": None, "first_seen": time.time()}, set())
    assert card["fit"] is None
    assert card["scored"] is False
    assert card["discoveryOnly"] is True
    assert card["hasJd"] is False
    assert card["variant"] is None, "an untailored role must not claim 'Default (safe master)'"


def test_role_card_does_not_present_a_title_derived_score_as_fit():
    """tailor_role falls back to scoring 'title + company' when there is no JD. That number
    describes the title, not the job — no JD, no fit score."""
    card = service.role_card(
        {"source_id": "li:2", "company": "Accenture", "title": "Product Owner",
         "source": "LinkedIn", "jd_text": "", "fit_hint": 4, "first_seen": time.time()}, set())
    assert card["scored"] is False
    assert card["fit"] is None


def test_role_card_keeps_a_real_score_for_a_real_jd():
    card = service.role_card(
        {"source_id": "gh:1", "company": "Stripe", "title": "PM", "source": "ATS",
         "jd_text": "payments platform api saas", "fit_hint": 5, "variant": "Platform / B2B",
         "first_seen": time.time()}, set())
    assert card["scored"] is True and card["fit"] == 5
    assert card["discoveryOnly"] is False
    assert card["variant"] == "Platform / B2B"


# ------------------------------------------------------- item 887: no-scraping rail
@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/comm/jobs/view/4448516228/",
    "https://linkedin.com/jobs/view/1",
    "HTTPS://WWW.LINKEDIN.COM/jobs/view/2",
])
def test_linkedin_urls_are_blocked_hosts(url):
    assert service.is_blocked_fetch_host(url) is True


@pytest.mark.parametrize("url", [
    "https://boards.greenhouse.io/stripe/jobs/1",
    "https://jobs.lever.co/meesho/abc",
    "https://notlinkedin.com/jobs/1",
])
def test_other_hosts_are_not_blocked(url):
    assert service.is_blocked_fetch_host(url) is False


def test_fetch_jd_from_linkedin_makes_no_request(monkeypatch):
    """REGRESSION: the Tailor-from-JD hand-off routed LinkedIn URLs into urlopen, breaching the
    locked non_goal on LinkedIn scraping. The guard belongs at the fetch boundary."""
    calls = []
    monkeypatch.setattr(service, "_get", lambda u, timeout=20: calls.append(u) or "")
    assert service.fetch_jd_from_url("https://www.linkedin.com/comm/jobs/view/999/") == ""
    assert calls == [], f"no request may be made to LinkedIn, but got {calls}"


def test_generate_pdf_refuses_a_linkedin_url_without_fetching(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "_get", lambda u, timeout=20: calls.append(u) or "")
    res = service.generate_pdf(url="https://www.linkedin.com/comm/jobs/view/999/")
    assert res["ok"] is False
    assert res.get("blocked_host") is True
    assert "paste" in res["error"].lower()
    assert calls == []


# ------------------------------------------------------- item 888: freshness guard
_OPEN_ENDED_BODY = r"""
\section{Experience}
\entry{Product Manager --- HSBC}{Jul 2024 -- Present}
\sub{Hyderabad, India}
"""
_CLOSED_BODY = r"""
\section{Experience}
\entry{Product Manager --- HSBC}{Jul 2024 -- Jun 2026}
\sub{Hyderabad, India}
"""


def _resume_dir(tmp_path, body):
    (tmp_path / "body.tex").write_text(body, encoding="utf-8")
    return tmp_path


def test_guard_warns_on_an_unreviewed_open_ended_role(tmp_path, monkeypatch):
    """The real failure: body.tex read 'Present' for two months after the owner left HSBC and
    every generated CV carried a false date."""
    monkeypatch.setattr(service, "RESUME_DIR", _resume_dir(tmp_path, _OPEN_ENDED_BODY))
    con = _mem_db()
    entries = service._open_ended_entries()
    assert entries and "HSBC" in entries[0]

    warns = service.resume_warnings(con)
    codes = [w["code"] for w in warns]
    assert "master-open-ended-unreviewed" in codes
    # Owner chose WARN, not block: nothing may be escalated above 'warn'.
    assert {w["level"] for w in warns} <= {"warn", "info"}


def test_guard_is_silent_on_a_closed_date_range(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RESUME_DIR", _resume_dir(tmp_path, _CLOSED_BODY))
    con = _mem_db()
    assert service._open_ended_entries() == []
    assert [w for w in service.resume_warnings(con)
            if w["code"] == "master-open-ended-unreviewed"] == []


def test_confirming_the_master_silences_the_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RESUME_DIR", _resume_dir(tmp_path, _OPEN_ENDED_BODY))
    con = _mem_db()
    assert any(w["code"] == "master-open-ended-unreviewed" for w in service.resume_warnings(con))
    service.mark_master_reviewed(con, "checked")
    assert not any(w["code"] == "master-open-ended-unreviewed"
                   for w in service.resume_warnings(con))


def test_warning_returns_after_the_review_interval_lapses(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RESUME_DIR", _resume_dir(tmp_path, _OPEN_ENDED_BODY))
    con = _mem_db()
    stale = time.time() - (service.MASTER_REVIEW_INTERVAL_DAYS + 1) * 86400
    settings_store.set_status(con, service.MASTER_REVIEW_KEY, {"at": stale})
    assert any(w["code"] == "master-open-ended-unreviewed" for w in service.resume_warnings(con))
