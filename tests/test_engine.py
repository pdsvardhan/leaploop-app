"""Engine unit tests — the deterministic core (no network, no IMAP, no DB file).
Covers the Stage-3 loose ends: tiering precision, gmail-confirm wiring, LinkedIn parsing,
plus the cleaner filter and the applied state machine.  Run: `pytest -q` from the repo root.
"""
import sqlite3, time

from engine import tiering, cleaner, gmail_confirm, db


# ---------------------------------------------------------------- tiering
def test_curated_tier_a_and_c():
    assert tiering._curated_tier("Razorpay") == "A"
    assert tiering._curated_tier("Meesho") == "A"
    assert tiering._curated_tier("Stripe") == "B"
    assert tiering._curated_tier("Paytm") == "C"          # pinned downgrade (BUILD_PLAN 4)


def test_curated_strips_corporate_suffixes():
    assert tiering._curated_tier("Razorpay Software Pvt Ltd") == "A"
    assert tiering._curated_tier("Goldman Sachs Services India") == "A"


def test_curated_no_loose_substring_false_positive():
    # "OLX" is curated Tier-A; a company merely containing the letters must NOT match.
    assert tiering._matches("OLX", "OLX India") is True
    assert tiering._matches("OLX", "Knolxom Analytics") is False
    assert tiering._curated_tier("Some Unknown Startup") is None


# ---------------------------------------------------------------- cleaner filter
def test_is_pm_role():
    assert cleaner.is_pm_role("Senior Product Manager") is True
    assert cleaner.is_pm_role("Associate Product Manager") is True
    assert cleaner.is_pm_role("Software Engineer") is False
    assert cleaner.is_pm_role("Product Marketing Manager") is False   # excluded
    assert cleaner.is_pm_role("Principal Product Manager") is False   # level out of band
    assert cleaner.is_pm_role("Program Manager") is False


def test_is_india():
    assert cleaner.is_india("Bengaluru, India") is True
    assert cleaner.is_india("Remote, India") is True
    assert cleaner.is_india("London, UK") is False
    assert cleaner.is_india("", "This role is based in India, fully remote.") is True


def test_min_years_required():
    f = cleaner.min_years_required
    assert f("We need 8+ years of product management experience.") == 8     # senior -> will be cut
    assert f("Minimum 5 years of experience in product.") == 5
    assert f("3-5 years of experience preferred.") == 3                     # range -> low end
    assert f("Looking for a PM with 6+ years experience.") == 6             # 6 is OK (not >6)
    assert f("5+ years product management, 8+ years overall experience.") == 8  # strictest wins
    assert f("Great role for a curious builder.") is None                  # no requirement stated
    assert f("Our company was founded 12 years ago.") is None              # not an exp requirement
    assert f("") is None


def test_is_recruiter():
    assert cleaner.is_recruiter("Talent Leads HR Solutions Pvt Ltd") is True
    assert cleaner.is_recruiter("ABC Staffing Services") is True
    assert cleaner.is_recruiter("Razorpay") is False


# ---------------------------------------------------------------- LinkedIn parse
LINKEDIN_SAMPLE = """
<html><body><table>
  <tr><td>
    <a href="https://www.linkedin.com/comm/jobs/view/3912345678/?trk=eml-jobs_alert">Senior Product Manager</a>
    <p>Razorpay &middot; Bengaluru, India</p>
  </td></tr>
  <tr><td>
    <a href="https://www.linkedin.com/jobs/view/3912000111/">Product Manager, Growth</a>
    <span>CRED &middot; Bengaluru, Karnataka</span>
  </td></tr>
  <tr><td>
    <a href="https://www.linkedin.com/comm/jobs/view/3912345678/?dup=1">Senior Product Manager</a>
  </td></tr>
</table></body></html>
"""


def test_parse_linkedin_extracts_title_company_url():
    roles = gmail_confirm.parse_linkedin_html(LINKEDIN_SAMPLE)
    assert len(roles) == 2                                  # third link de-duped by job id
    first = roles[0]
    assert first["title"] == "Senior Product Manager"
    assert first["company"] == "Razorpay"
    assert first["url"] == "https://www.linkedin.com/comm/jobs/view/3912345678/"
    assert first["source"] == "LinkedIn"
    assert first["source_id"] == "li:3912345678"
    assert roles[1]["company"] == "CRED"


def test_company_from_confirmation_subject():
    assert gmail_confirm._company_from("noreply@x.com",
                                       "your application was sent to Navi") == "Navi"
    assert gmail_confirm._company_from("careers@razorpay.com",
                                       "We received your application") == "Razorpay"


# ---------------------------------------------------------------- applied state machine
def _mem_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    db.init_db(con)
    return con


def _seed_role(con, sid="gh:cred:1", company="Cred", title="Product Manager, Growth", state="picked"):
    db.upsert_role(con, {"source_id": sid, "company": company, "title": title,
                         "location": "Bengaluru", "source": "ATS", "tier": "A"})
    db.set_state(con, sid, state)


def test_mark_applied_and_undo():
    con = _mem_db()
    _seed_role(con)
    row = db.mark_applied(con, "gh:cred:1", True)
    assert row["applied"] == 1 and row["state"] == "applied" and row["applied_at"]
    row = db.mark_applied(con, "gh:cred:1", False)            # manual override / undo
    assert row["applied"] == 0 and row["state"] == "picked" and row["applied_at"] is None


def test_find_active_by_company_normalizes_casing():
    con = _mem_db()
    _seed_role(con, company="Cred")
    # confirmation email says "CRED" (different casing) — must still find the role.
    found = db.find_active_by_company(con, "CRED")
    assert len(found) == 1 and found[0]["source_id"] == "gh:cred:1"
    db.mark_applied(con, "gh:cred:1", True)
    assert db.find_active_by_company(con, "CRED") == []        # applied roles excluded


def test_snooze_sets_state_and_future_until():
    con = _mem_db()
    _seed_role(con, sid="gh:x:1", state="triage")
    db.snooze(con, "gh:x:1", hours=12)
    row = dict(con.execute("SELECT * FROM roles WHERE source_id='gh:x:1'").fetchone())
    assert row["state"] == "snoozed"
    assert row["snoozed_until"] and row["snoozed_until"] > time.time()
