"""Cleaner: filter to India PM roles, drop excludes/levels-out, dedupe, drop already-applied, tier."""
from __future__ import annotations
import re
try:
    from . import config, db, tiering, settings_store
except ImportError:
    import config, db, tiering, settings_store


def _has_any(text: str, terms) -> bool:
    t = (text or "").lower()
    return any(term in t for term in terms)


def is_india(location: str, jd_text: str = "") -> bool:
    loc = (location or "").lower()
    if any(h in loc for h in config.INDIA_LOCATION_HINTS):
        return True
    # fallback: explicit India mention in the JD body (some feeds omit structured location)
    return "india" in (jd_text or "").lower()[:400]


NON_PM_TITLES = ("software", "engineer", "developer", "sde", "sdet", "architect", "designer",
                 "data scientist", "analyst", "qa", "devops", "sales", "recruit", "marketing",
                 "accountant", "consultant", "researcher", "scientist", "operations manager")


def is_pm_role(title: str, excludes=None) -> bool:
    t = (title or "").lower()
    if _has_any(t, excludes if excludes is not None else config.EXCLUDE_KEYWORDS):
        return False
    if _has_any(t, config.LEVELS_OUT):       # Lead/Principal/Group/Director+ out (his locked band)
        return False
    # Require a real PM signal (word-boundary pm/apm, not substring of "pml"/"pmo").
    has_signal = bool(
        "product manager" in t or "product management" in t or "product owner" in t
        or re.search(r"\b(a?pm)\b", t) or _has_any(t, config.ROLE_SECONDARY)
    )
    if not has_signal:
        return False
    # Reject non-PM tech/biz titles unless they explicitly mention "product".
    if any(w in t for w in NON_PM_TITLES) and "product" not in t:
        return False
    return True


_EXP_KEYWORDS = ("experience", "minimum", "at least", "product manage", "managing", "leadership",
                 "overall", "relevant", "industry", "of work", "prior", "hands-on", "yrs", "yoe")
_YEAR_RE = re.compile(r"(\d{1,2})\s*(\+)?\s*(?:to|[-–—])?\s*(\d{1,2})?\s*(\+)?\s*years?", re.I)


def min_years_required(jd_text: str):
    """Strictest years-of-experience the JD requires (None if unstated / no JD).

    For a range ("3-5 years") takes the low end; for "X+ years" takes X; returns the MAX such
    floor across the JD (you must satisfy the strictest requirement). A bare "X years" only counts
    near an experience keyword; an explicit "X+ years" always counts. Cuts senior roles (e.g. an
    8-year JP Morgan posting) while keeping anything you plausibly qualify for.
    """
    jd = (jd_text or "").lower()
    if not jd:
        return None
    floors = []
    for m in _YEAR_RE.finditer(jd):
        lo = int(m.group(1))
        if not (1 <= lo <= 30):
            continue
        has_plus = bool(m.group(2) or m.group(4))
        ctx = jd[max(0, m.start() - 55): m.end() + 25]
        if has_plus or any(k in ctx for k in _EXP_KEYWORDS):
            floors.append(lo)
    return max(floors) if floors else None


def is_recruiter(company: str) -> bool:
    """Third-party staffing/recruiter listing, not the real employer."""
    c = (company or "").lower()
    return any(p in c for p in getattr(config, "RECRUITER_PATTERNS", []))


def _key(company: str, title: str):
    return (re.sub(r"\W+", "", (company or "").lower()), re.sub(r"\W+", "", (title or "").lower()))


def clean(roles, con=None):
    """Returns the cleaned, tiered, de-duped shortlist (excludes already-applied).

    Honors Settings-screen edits when a DB connection is given: extra exclude keywords and
    watch-list tier pins are read once per cycle (so a change takes effect on the next poll).
    """
    excludes = settings_store.effective_excludes(con) if con is not None else None
    overrides = settings_store.effective_curated(con) if con is not None else None
    muted = settings_store.effective_muted(con) if con is not None else set()
    cap = getattr(config, "MAX_YEARS_EXPERIENCE", 6)
    existing = {}                                                       # repost dedup
    if con is not None:
        for sid, co, ti in db.all_role_idents(con):
            existing[_key(co, ti)] = sid
    seen, out = set(), []
    for r in roles:
        title, loc = r.get("title", ""), r.get("location", "")
        company, sid = r.get("company", ""), r.get("source_id", "")
        if muted and db.norm(company) in muted:
            continue
        if not is_pm_role(title, excludes):
            continue
        if not is_india(loc, r.get("jd_text", "")):
            continue
        # Experience gate: drop roles whose JD clearly requires more than the cap (e.g. 8+ yrs).
        req = min_years_required(r.get("jd_text", ""))
        if req is not None and req > cap:
            continue
        k = _key(company, title)
        if k in seen:
            continue
        seen.add(k)
        # Repost dedup: same company+title already stored under a DIFFERENT id (reposted role).
        if k in existing and existing[k] != sid:
            continue
        if con is not None and db.already_applied(con, company, title):
            continue
        r["tier"] = tiering.tier_of(company, con, overrides)
        out.append(r)
    return out
