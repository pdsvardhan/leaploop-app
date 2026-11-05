"""Tests for iteration 170 — the tailoring-engine audit fixes and the five open to-dos.

Every test maps to a locked item. The ones marked MEASURED encode a defect that was measured
against the 139 real JDs stored in the live DB on 2026-09-04, so the numbers in the docstrings
are observations, not estimates.
Run: `pytest -q` from the repo root.
"""
import imaplib
import time
import sqlite3

import pytest

from engine import db, gmail_confirm, settings_store, tailor
from cockpit.api import service

RULES = tailor.load_rules()


def _mem_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    db.init_db(con)
    return con


# ------------------------------------------------- item 1215: word-aware matching
def test_ai_does_not_match_inside_ordinary_words():
    """MEASURED: `"ai" in jd` fired inside mainstream(35) domain(12) brainstorming(10)
    daily(9) available(9) entertainment(9) detailed(8) across 38 of 139 real JDs, which is
    what put an AI-native CV in front of JDs that never mentioned AI."""
    noise = "mainstream domain brainstorming daily available entertainment detailed retail"
    assert tailor.matches("ai", noise) is False


def test_ai_still_matches_where_it_is_meant_to():
    assert tailor.matches("ai", "we are building ai products") is True
    assert tailor.matches("ai", "an ai-powered assistant") is True      # hyphenated compound
    assert tailor.matches("ai", "AI".lower()) is True


def test_api_does_not_match_inside_capital_or_rapid():
    """MEASURED: 'api' fired inside capital(18) and rapid(8)."""
    assert tailor.matches("api", "capital markets in a rapid, rapidly growing team") is False
    assert tailor.matches("api", "design the public api") is True
    assert tailor.matches("api", "our apis are documented") is True     # inflected plural


def test_inflections_still_count():
    assert tailor.matches("agent", "agentic workflows") is True
    assert tailor.matches("agent", "our agents handle cases") is True
    assert tailor.matches("consumer", "consumers first") is True
    assert tailor.matches("a/b test", "we run a/b testing weekly") is True


# ------------------------------------------------- item 1216: gap detection
def test_rag_gap_not_fired_by_average_or_leverage():
    """MEASURED: the ml_modeling keyword 'rag' matched inside average(23) and leverage(8),
    flagging a fabricated ML-modeling gap on 30 of 139 JDs."""
    jd = "leverage the average order value across the funnel"
    gaps = tailor.detect_gaps(jd, RULES)
    assert "ml_modeling" not in gaps


def test_rag_gap_still_fires_on_a_real_mention():
    assert "ml_modeling" in tailor.detect_gaps("experience with rag pipelines", RULES)


# ------------------------------------------------- item 1217: domain-first scoring
def test_process_cluster_never_beats_a_domain_cluster():
    """MEASURED: 'roadmap' appeared in 101 of 139 JDs and 'delivery' in 96, so agile_delivery
    won 53% of every JD on words that carry no domain signal at all."""
    jd = ("own the roadmap and delivery, run sprint demos, groom the backlog with scrum, "
          "write user stories in jira as the product owner — the platform handles payments "
          "settlement and reconciliation")
    cluster, _ = tailor.choose_cluster(jd, RULES)
    assert cluster["name"] == "fintech_payments"


def test_process_cluster_still_wins_when_nothing_domain_specific_matches():
    jd = "own the roadmap and delivery cadence, run sprint demos and groom the backlog"
    cluster, _ = tailor.choose_cluster(jd, RULES)
    assert cluster["name"] == "agile_delivery"


def test_bfsi_can_now_win():
    """bfsi_compliance won 0 of 139 JDs before this change despite being the closest match to
    the actual HSBC collections background."""
    jd = ("a regulated bfsi platform: compliance, governance, audit trails and collections "
          "workflows for a bank, with roadmap and delivery ownership")
    cluster, _ = tailor.choose_cluster(jd, RULES)
    assert cluster["name"] == "bfsi_compliance"


def test_title_hits_outweigh_a_single_body_mention():
    jd = "you will partner with analytics teams and look at dashboard metrics"
    assert tailor.choose_cluster(jd, RULES)[0]["name"] == "data_product"
    # The same body, but the title says what the job actually is.
    cluster, _ = tailor.choose_cluster(jd, RULES, title="Senior Product Manager, Payments")
    assert cluster["name"] == "fintech_payments"


def test_empty_jd_falls_back_to_the_safe_master():
    res = tailor.render_tex("", title="")
    assert res["cluster"] == "default"
    assert res["fit_hint"] == 0


# ------------------------------------------------- item 1220: LaTeX escaping
def test_user_override_values_are_latex_escaped():
    """A chip value containing & % $ # _ produced a LaTeX error instead of a PDF."""
    res = tailor.render_tex("", override={"descriptor": "R&D 100% cost_centre #1 $x"})
    ov = res["overrides"]
    assert r"\&" in ov and r"\%" in ov and r"\_" in ov and r"\#" in ov and r"\$" in ov
    assert "R&D" not in ov          # the raw ampersand must not survive


def test_rules_authored_latex_is_not_escaped():
    """p5 bullets are authored LaTeX — escaping them would print the macros verbatim."""
    res = tailor.render_tex("payments settlement reconciliation upi")
    assert r"\item" in res["overrides"]
    assert r"\textbackslash" not in res["overrides"]


def test_sanitize_override_rejects_unknown_p5_and_third_project():
    out = tailor.sanitize_override({"p5": "not_a_real_bullet", "third_project": "../etc",
                                    "descriptor": "enterprise"}, RULES)
    assert "p5" not in out and "third_project" not in out
    assert out["descriptor"] == "enterprise"


def test_sanitize_override_stores_raw_so_it_round_trips():
    """Escaping happens at render time, not on save — otherwise a value picks up another
    backslash every time it passes through the editor."""
    out = tailor.sanitize_override({"domain_add": ", R&D"}, RULES)
    assert out["domain_add"] == ", R&D"


def test_unknown_p5_key_falls_back_to_the_default_bullet():
    """An unknown key used to drop the \\flexHSBCFive renewcommand entirely and silently
    leave the preamble default in place."""
    ov = tailor.build_overrides({"p5": "nope"}, RULES)
    assert r"\renewcommand{\flexHSBCFive}" in ov


# ------------------------------------------------- item 1227: P5-D / P5-G wiring
def test_confirmed_p5_bullets_are_wired_to_their_clusters():
    """Confirmed by the owner 2026-09-04; before that both sat in rules.yaml unreferenced."""
    fin = tailor.cluster_by_name("fintech_payments", RULES)
    dat = tailor.cluster_by_name("data_product", RULES)
    assert fin["p5"] == "fintech_commission"
    assert dat["p5"] == "data_decisioning"
    tex = tailor.render_tex("upi settlement reconciliation lending underwriting")["tex"]
    assert "commission and invoicing engine" in tex


# ------------------------------------------------- item 1221: variants from rules
def test_variant_list_is_derived_from_rules_not_hardcoded():
    names = {o["name"] for o in tailor.variant_options(RULES)}
    assert names == {"default"} | {c["name"] for c in RULES["clusters"]}
    assert service.name_to_label("bfsi_compliance") == "BFSI / compliance"
    assert service.label_to_name("BFSI / compliance") == "bfsi_compliance"
    assert "Fintech / payments" in service.variant_labels()


def test_unknown_variant_label_maps_to_the_master_not_a_crash():
    assert service.name_to_label("not_a_cluster") == "Default (safe master)"
    assert service.label_to_name("Custom (edited)") is None


# ------------------------------------------------- item 1219: chip round-trip
def test_saved_overrides_round_trip_out_of_the_row():
    con = _mem_db()
    db.upsert_role(con, {"source_id": "gh:acme:1", "company": "Acme", "title": "PM",
                         "jd_text": "payments upi", "tier": "A"})
    con.execute("UPDATE roles SET variant='Custom (edited)', overrides_json=? WHERE source_id=?",
                ('{"descriptor": "enterprise and fintech", "p5": "bfsi_docs"}', "gh:acme:1"))
    con.commit()
    row = dict(con.execute("SELECT * FROM roles WHERE source_id='gh:acme:1'").fetchone())
    saved = service._saved_overrides(row["overrides_json"])
    assert saved["p5"] == "bfsi_docs"
    # 'Custom (edited)' maps to no cluster, so without the saved dict the editor would have
    # reseeded from the default cluster and dropped the user's edit.
    assert service._seed_overrides("Custom (edited)", RULES)["p5"] == RULES["default"]["p5"]


def test_saved_overrides_ignores_junk():
    assert service._saved_overrides(None) is None
    assert service._saved_overrides("{not json") is None
    assert service._saved_overrides("{}") is None


def test_roles_table_has_the_overrides_column():
    con = _mem_db()
    cols = {r[1] for r in con.execute("PRAGMA table_info(roles)")}
    assert "overrides_json" in cols


def test_migration_adds_the_column_to_an_older_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE roles (source_id TEXT PRIMARY KEY, company TEXT, title TEXT, "
                "jd_text TEXT, fit_hint INTEGER)")
    db.init_db(con)
    cols = {r[1] for r in con.execute("PRAGMA table_info(roles)")}
    assert "overrides_json" in cols


# ------------------------------------------------- to-do #420: manual-generate dedupe
def test_manual_generate_applied_row_makes_the_cleaner_drop_the_role():
    """cleaner.clean (engine/cleaner.py:120) drops anything already in applied_index, so the
    row written by log_generated_applied is what stops a manually-applied role resurfacing."""
    con = _mem_db()
    assert db.already_applied(con, "Razorpay", "Senior Product Manager") is False
    db.add_applied(con, "Razorpay", "Senior Product Manager",
                   resume="cv.pdf", source="manual-generate")
    assert db.already_applied(con, "razorpay", "senior product manager") is True


# ------------------------------------------------- to-do #421: IMAP reconnect
class _FakeIMAP:
    def __init__(self):
        self.selected = None
        self.logged_out = False

    def select(self, mailbox):
        self.selected = mailbox
        return ("OK", [b"1"])

    def logout(self):
        self.logged_out = True


def test_session_reconnects_once_on_a_dead_socket(monkeypatch):
    """REGRESSION: with_retry re-ran the operation on the SAME connection, so after an
    IMAP4.abort (the socket-EOF symptom) all three attempts were guaranteed to fail."""
    made = []
    monkeypatch.setattr(gmail_confirm, "connect", lambda: made.append(_FakeIMAP()) or made[-1])
    sess = gmail_confirm.Session()
    sess.select("INBOX")
    seen = []

    def op(m):
        seen.append(m)
        if len(seen) == 1:
            raise imaplib.IMAP4.abort("socket error: EOF")
        return "ok"

    assert sess.call(op, base_delay=0) == "ok"
    assert sess.reconnects == 1
    assert len(made) == 2                 # a fresh connection, not the corpse
    assert seen[1] is made[1]             # the retry ran on the new one
    assert made[1].selected == "INBOX"    # and the mailbox was re-selected
    assert made[0].logged_out is True     # the dead one was closed


def test_session_does_not_reconnect_forever(monkeypatch):
    made = []
    monkeypatch.setattr(gmail_confirm, "connect", lambda: made.append(_FakeIMAP()) or made[-1])
    sess = gmail_confirm.Session()
    attempts = []

    def always_abort(m):
        attempts.append(m)
        raise imaplib.IMAP4.abort("socket error: EOF")

    with pytest.raises(imaplib.IMAP4.abort):
        sess.call(always_abort, base_delay=0)
    assert len(attempts) == 2             # one on the original, one on the replacement
    assert sess.reconnects == 1


def test_close_quietly_accepts_a_session_or_a_raw_connection():
    m = _FakeIMAP()
    gmail_confirm.close_quietly(m)
    assert m.logged_out is True
    sess = gmail_confirm.Session(_FakeIMAP())
    gmail_confirm.close_quietly(sess)
    assert sess.m.logged_out is True
    gmail_confirm.close_quietly(None)     # must not raise


# ------------------------------------------------- applied log must be undoable
def test_applied_log_can_be_undone():
    """Found during live verification: the first version wrote an applied_index row with no
    way to remove it, so one mis-click permanently claimed an application that never happened."""
    con = _mem_db()
    db.add_applied(con, "Acme Payments", "Senior Product Manager", source="manual-generate")
    assert db.already_applied(con, "Acme Payments", "Senior Product Manager") is True
    assert db.remove_applied(con, "Acme Payments", "Senior Product Manager") == 1
    assert db.already_applied(con, "Acme Payments", "Senior Product Manager") is False


def test_remove_applied_is_a_no_op_when_there_is_nothing_to_remove():
    con = _mem_db()
    assert db.remove_applied(con, "Nobody", "Nothing") == 0


# ------------------------------------------------- to-do #423 fallout
def test_imap_auth_failure_is_not_retried():
    """MEASURED: the forced-failure run spent 10.8s retrying a rejected app password three
    times — an error that cannot clear by waiting, and three more bad logins sent to Gmail."""
    calls = []

    def bad_login():
        calls.append(1)
        raise imaplib.IMAP4.error("b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'")

    with pytest.raises(imaplib.IMAP4.error):
        gmail_confirm.with_retry(bad_login, base_delay=0)
    assert len(calls) == 1


def test_transient_imap_failure_is_still_retried():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise imaplib.IMAP4.error("System Error")
        return "ok"

    assert gmail_confirm.with_retry(flaky, base_delay=0) == "ok"
    assert len(calls) == 3


def test_session_does_not_reconnect_on_an_auth_failure(monkeypatch):
    made = []
    monkeypatch.setattr(gmail_confirm, "connect", lambda: made.append(_FakeIMAP()) or made[-1])
    sess = gmail_confirm.Session()

    def bad(m):
        raise imaplib.IMAP4.error("b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'")

    with pytest.raises(imaplib.IMAP4.error):
        sess.call(bad, base_delay=0)
    assert sess.reconnects == 0 and len(made) == 1


def test_recorded_integration_error_is_not_a_bytes_repr():
    """The Settings row rendered b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'
    straight at the user, quotes, b-prefix and all."""
    con = _mem_db()
    db.record_integration(con, "gmail-confirm", False,
                          "b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'")
    err = {r["name"]: r for r in db.get_integrations(con)}["gmail-confirm"]["last_error"]
    assert err == "[AUTHENTICATIONFAILED] Invalid credentials (Failure)"


def test_integration_status_reports_broken_then_failing(monkeypatch):
    """Both branches of the honest-status logic, end to end (to-do #423)."""
    monkeypatch.setattr(gmail_confirm, "_secrets",
                        lambda: {"GMAIL_USER": "u@example.com", "GMAIL_APP_PASSWORD": "x"})
    con = _mem_db()
    db.record_integration(con, "gmail-confirm", False, "nope")
    leg = {l["name"]: l for l in service.integration_status(con)["legs"]}["gmail-confirm"]
    assert leg["status"] == "failed" and leg["healthy"] is False      # never worked -> Broken
    con.execute("UPDATE integration_health SET last_success=? WHERE name=?",
                (time.time() - 3600, "gmail-confirm"))
    con.commit()
    leg = {l["name"]: l for l in service.integration_status(con)["legs"]}["gmail-confirm"]
    assert leg["status"] == "degraded"                                # worked 1h ago -> Failing


# ------------------------------------------------- verifier finding P1: applied-row ownership
def _fake_meta(monkeypatch, meta):
    monkeypatch.setattr(service, "_generated_meta", lambda t: meta)
    monkeypatch.setattr(service, "_write_generated_meta", lambda t, m: meta.update(m))


def test_log_applied_never_overwrites_someone_elses_row(monkeypatch):
    """REGRESSION (found by the iter-170 verifier): add_applied is INSERT OR REPLACE on
    (company_norm, title_norm), so logging a company already in the tracker replaced a real
    gmail-confirm row's résumé, source and date."""
    con = _mem_db()
    db.add_applied(con, "Razorpay", "Senior Product Manager",
                   resume="pdfs/gh_rzp_1/cv.pdf", source="gmail-confirm", date="2026-07-01")
    _fake_meta(monkeypatch, {"company": "Razorpay", "title": "Senior Product Manager"})
    monkeypatch.setattr(db, "connect", lambda: con)

    res = service.log_generated_applied("tok")
    assert res["ok"] is True and res["already_tracked"] is True
    row = dict(con.execute("SELECT * FROM applied_index WHERE company_norm='razorpay'").fetchone())
    assert row["source"] == "gmail-confirm"          # untouched
    assert row["resume"] == "pdfs/gh_rzp_1/cv.pdf"
    assert row["date"] == "2026-07-01"


def test_undo_never_deletes_a_row_it_did_not_write(monkeypatch):
    """REGRESSION: the first undo deleted on company+title with no ownership check. 48 of the
    54 live applied_index rows have no matching role, so that row is their only copy."""
    con = _mem_db()
    db.add_applied(con, "Razorpay", "Senior Product Manager", source="gmail-confirm")
    _fake_meta(monkeypatch, {"company": "Razorpay", "title": "Senior Product Manager"})
    monkeypatch.setattr(db, "connect", lambda: con)

    service.log_generated_applied("tok")
    res = service.unlog_generated_applied("tok")
    assert res["ok"] is True and res["removed"] == 0 and res["kept_existing"] is True
    assert db.already_applied(con, "Razorpay", "Senior Product Manager") is True


def _fake_generated_pdf(tmp_path, token):
    """The résumé has to be on disk — the row records this token's own path, and undo reads
    that path back to decide whether the row is still its own."""
    d = tmp_path / "pdfs" / f"_generated_{token}"
    d.mkdir(parents=True, exist_ok=True)
    (d / service.config.PDF_OUTPUT_NAME).write_bytes(b"%PDF-1.5\n")


def test_undo_does_remove_the_row_it_wrote(monkeypatch, tmp_path):
    con = _mem_db()
    _fake_meta(monkeypatch, {"company": "Verify Co", "title": "Product Manager"})
    monkeypatch.setattr(db, "connect", lambda: con)
    monkeypatch.setattr(service, "DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "PDF_ROOT", tmp_path / "pdfs")
    _fake_generated_pdf(tmp_path, "tok123")

    res = service.log_generated_applied("tok123")
    assert res["already_tracked"] is False
    row = dict(con.execute("SELECT * FROM applied_index WHERE company_norm='verify co'").fetchone())
    assert row["source"] == "manual-generate"
    # the row points at THIS résumé, not just the constant filename
    assert "_generated" in row["resume"] and row["resume"].endswith(service.config.PDF_OUTPUT_NAME)

    res = service.unlog_generated_applied("tok123")
    assert res["removed"] == 1 and res["kept_existing"] is False
    assert db.already_applied(con, "Verify Co", "Product Manager") is False


def test_undo_twice_is_refused(monkeypatch, tmp_path):
    con = _mem_db()
    _fake_meta(monkeypatch, {"company": "Verify Co", "title": "Product Manager"})
    monkeypatch.setattr(db, "connect", lambda: con)
    monkeypatch.setattr(service, "DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "PDF_ROOT", tmp_path / "pdfs")
    _fake_generated_pdf(tmp_path, "tok123")
    service.log_generated_applied("tok123")
    assert service.unlog_generated_applied("tok123")["ok"] is True
    assert service.unlog_generated_applied("tok123")["ok"] is False


# ------------------------------------------------- verifier finding P4: silent drops
def test_sanitize_override_says_what_it_dropped():
    notes = []
    out = tailor.sanitize_override(
        {"p5": "nope", "third_project": "../etc", "descriptor": "x" * 260,
         "domain_add": ", B2B"}, RULES, notes=notes)
    assert len(out["descriptor"]) == tailor.MAX_OVERRIDE_LEN
    assert out["domain_add"] == ", B2B"
    assert any("confirmed 5th bullet" in n for n in notes)
    assert any("known third project" in n for n in notes)
    assert any("trimmed" in n for n in notes)


def test_sanitize_override_is_quiet_when_nothing_was_dropped():
    notes = []
    tailor.sanitize_override({"descriptor": "enterprise and fintech", "p5": "allocation"},
                             RULES, notes=notes)
    assert notes == []


# ------------------------------------------------- verifier finding P6: reconnect budget
def _conn_factory(made):
    def make():
        made.append(_FakeIMAP())
        return made[-1]
    return make


def test_reconnect_budget_is_per_operation_not_per_session(monkeypatch):
    """A session that healed on its first operation used to be defenceless on every later
    one — self.reconnects was never reset."""
    made = []
    monkeypatch.setattr(gmail_confirm, "connect", _conn_factory(made))
    sess = gmail_confirm.Session()

    def op_failing_on(dead):
        def op(m):
            if m is dead:
                raise imaplib.IMAP4.abort("socket error: EOF")
            return "ok"
        return op

    assert sess.call(op_failing_on(made[0]), base_delay=0) == "ok"
    assert sess.reconnects == 1
    assert sess.call(op_failing_on(made[1]), base_delay=0) == "ok"   # its own budget
    assert sess.reconnects == 2


def test_reconnect_budget_is_capped_for_the_session(monkeypatch):
    made = []
    monkeypatch.setattr(gmail_confirm, "connect", _conn_factory(made))
    monkeypatch.setattr(gmail_confirm, "MAX_RECONNECTS", 1)
    sess = gmail_confirm.Session()

    def always_abort(m):
        raise imaplib.IMAP4.abort("socket error: EOF")

    with pytest.raises(imaplib.IMAP4.abort):
        sess.call(always_abort, base_delay=0)
    assert sess.reconnects == 1
    with pytest.raises(imaplib.IMAP4.abort):
        sess.call(always_abort, base_delay=0)
    assert sess.reconnects == 1          # capped, no endless reconnect loop


# ------------------------------------------------- verifier finding P11
def test_matches_is_case_insensitive_on_both_sides():
    assert tailor.matches("payments", "Own the Payments Platform") is True
    assert tailor.matches("ai", "AI-Powered Assistant") is True
    assert tailor.matches("ai", "Mainstream Domain Available") is False


# ------------------------------------------------- re-verifier findings #1 and #2
def test_undo_will_not_delete_a_row_that_was_replaced_by_a_real_confirmation(monkeypatch, tmp_path):
    """REGRESSION (re-verifier #1): remembering that we created a row is not the same as the
    row still being ours. gmail_confirm and the Apply screen both write with INSERT OR REPLACE
    on the same primary key, so a row we created can be replaced by a genuine confirmation —
    and deleting that is P1 again, just narrower."""
    con = _mem_db()
    _fake_meta(monkeypatch, {"company": "Verify Co", "title": "Product Manager"})
    monkeypatch.setattr(db, "connect", lambda: con)
    monkeypatch.setattr(service, "DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "PDF_ROOT", tmp_path / "pdfs")
    _fake_generated_pdf(tmp_path, "tokX")

    service.log_generated_applied("tokX")
    assert db.already_applied(con, "Verify Co", "Product Manager") is True

    # a real confirmation email lands and replaces the row
    db.add_applied(con, "Verify Co", "Product Manager",
                   resume="pdfs/li_998877/cv.pdf", source="gmail-confirm")

    res = service.unlog_generated_applied("tokX")
    assert res["removed"] == 0 and res["kept_existing"] is True
    row = db.get_applied(con, "Verify Co", "Product Manager")
    assert row["source"] == "gmail-confirm" and row["resume"] == "pdfs/li_998877/cv.pdf"


def test_logging_twice_does_not_make_the_row_un_undoable(monkeypatch, tmp_path):
    """REGRESSION (re-verifier #2): the first guard flipped its own ownership flag to False on
    a second log, stranding a row nothing could remove."""
    con = _mem_db()
    _fake_meta(monkeypatch, {"company": "Verify Co", "title": "Product Manager"})
    monkeypatch.setattr(db, "connect", lambda: con)
    monkeypatch.setattr(service, "DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "PDF_ROOT", tmp_path / "pdfs")
    _fake_generated_pdf(tmp_path, "tokY")

    service.log_generated_applied("tokY")
    service.log_generated_applied("tokY")            # second click / direct API call
    res = service.unlog_generated_applied("tokY")
    assert res["removed"] == 1 and res["kept_existing"] is False
    assert db.already_applied(con, "Verify Co", "Product Manager") is False


def test_another_tokens_row_is_not_ours(monkeypatch, tmp_path):
    con = _mem_db()
    db.add_applied(con, "Verify Co", "Product Manager",
                   resume="pdfs/_generated_someoneelse/cv.pdf", source="manual-generate")
    _fake_meta(monkeypatch, {"company": "Verify Co", "title": "Product Manager",
                             "applied_at": "2026-09-04 22:00"})
    monkeypatch.setattr(db, "connect", lambda: con)
    monkeypatch.setattr(service, "DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "PDF_ROOT", tmp_path / "pdfs")
    res = service.unlog_generated_applied("tokZ")
    assert res["removed"] == 0 and res["kept_existing"] is True


# ------------------------------------------------- re-verifier finding #5
def test_read_paths_do_not_create_directories(monkeypatch, tmp_path):
    """A bogus token used to litter data/pdfs with empty directories, because pdf_dir_for
    mkdir'd on lookup."""
    monkeypatch.setattr(service, "DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "PDF_ROOT", tmp_path / "pdfs")
    assert service.generated_edit_state("nosuchtoken") is None
    assert service._generated_meta("nosuchtoken") == {}
    assert service._generated_pdf_rel("nosuchtoken") is None
    assert not (tmp_path / "pdfs" / "_generated_nosuchtoken").exists()


def test_applied_row_never_points_at_a_pdf_that_is_not_there(monkeypatch, tmp_path):
    con = _mem_db()
    _fake_meta(monkeypatch, {"company": "Ghost Co", "title": "Product Manager"})
    monkeypatch.setattr(db, "connect", lambda: con)
    monkeypatch.setattr(service, "DATA_DIR", tmp_path)
    monkeypatch.setattr(service, "PDF_ROOT", tmp_path / "pdfs")
    service.log_generated_applied("missingpdf")          # no PDF written for this token
    row = db.get_applied(con, "Ghost Co", "Product Manager")
    assert row["resume"] == service.config.PDF_OUTPUT_NAME    # the honest fallback
    assert not (tmp_path / "pdfs" / "_generated_missingpdf").exists()


# ------------------------------------------------- adr-011: downloaded filename
def test_download_name_carries_the_company():
    con = _mem_db()
    name = service.download_filename("Razorpay", con)
    assert name == "Sai_Vardhan_Palli_Product_Manager_IIMB_CV_Razorpay.pdf"
    assert name != service.config.PDF_OUTPUT_NAME


def test_company_slug_is_filesystem_safe_and_bounded():
    assert service.company_slug("Airtel Digital") == "AirtelDigital"
    assert service.company_slug("Ernst & Young / India") == "ErnstYoungIndia"
    assert service.company_slug("../../etc/passwd") == "etcpasswd"
    assert len(service.company_slug("A" * 80)) == service.MAX_COMPANY_SLUG
    assert service.company_slug("!!!") == ""


def test_master_one_pager_keeps_the_plain_name():
    """No company means the clean in-hand résumé — that one stays constant."""
    con = _mem_db()
    assert service.download_filename("", con) == service.config.PDF_OUTPUT_NAME
    assert service.download_filename("!!!", con) == service.config.PDF_OUTPUT_NAME


def test_the_owner_can_turn_it_off():
    con = _mem_db()
    settings_store.put_settings(con, {"nameWithCompany": False})
    assert service.download_filename("Razorpay", con) == service.config.PDF_OUTPUT_NAME
    settings_store.put_settings(con, {"nameWithCompany": True})
    assert service.download_filename("Razorpay", con).endswith("_Razorpay.pdf")


def test_a_settings_failure_never_breaks_a_download():
    """A download is the last step before applying; it must not depend on a settings read."""
    class Boom:
        def execute(self, *a, **k):
            raise RuntimeError("db gone")
    assert service.download_filename("Razorpay", Boom()).endswith("_Razorpay.pdf")


def test_two_roles_in_one_sitting_get_different_names():
    """The whole point: Chrome only appends (1) when the name collides."""
    con = _mem_db()
    a = service.download_filename("Razorpay", con)
    b = service.download_filename("PhonePe", con)
    assert a != b and a.endswith("_Razorpay.pdf") and b.endswith("_PhonePe.pdf")
