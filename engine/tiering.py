"""Company reputation tiering: curated Tier-A/B (config) override Wikidata-derived B/C; else U.
Wikidata is keyless. Result cached in company_tier. NEVER blocks the pipeline on a lookup failure.
"""
from __future__ import annotations
import json, re, urllib.parse, urllib.request

try:
    from . import config, db
except ImportError:
    import config, db

UA = {"User-Agent": "Mozilla/5.0 (LeapLoop/1.0; personal job radar)"}

# Common corporate suffixes stripped before matching so "Razorpay" == "Razorpay Software Pvt Ltd".
_SUFFIXES = {"inc", "ltd", "limited", "llc", "llp", "pvt", "private", "plc", "corp",
             "corporation", "co", "company", "technologies", "technology", "labs",
             "india", "global", "tech", "services", "solutions", "softwares", "software"}


def _norm_tokens(name: str) -> list[str]:
    toks = re.split(r"[^a-z0-9]+", (name or "").lower())
    return [t for t in toks if t and t not in _SUFFIXES]


def _matches(curated: str, name: str) -> bool:
    """True if `name` is the curated company. Word-aware, not a loose substring.

    Matches when the curated token-set is a contiguous run inside the company's token-set
    (so "Goldman Sachs" matches "Goldman Sachs Services India" but "OLX" does NOT match
    a company that merely happens to contain the letters o-l-x).
    """
    c, n = _norm_tokens(curated), _norm_tokens(name)
    if not c or not n:
        return False
    if c == n:
        return True
    for i in range(len(n) - len(c) + 1):       # contiguous subsequence
        if n[i:i + len(c)] == c:
            return True
    return False


def _curated_tier(name: str) -> str | None:
    for c in config.TIER_A:
        if _matches(c, name):
            return "A"
    for b in config.TIER_B:
        if _matches(b, name):
            return "B"
    for cc in getattr(config, "TIER_C", []):
        if _matches(cc, name):
            return "C"
    return None


def _wikidata_employees(name: str):
    """Return (found: bool, employees: int|None). Keyless Wikidata REST."""
    try:
        q = urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": "en",
                                    "format": "json", "type": "item", "limit": 1})
        req = urllib.request.Request("https://www.wikidata.org/w/api.php?" + q, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            hits = json.loads(r.read().decode()).get("search", [])
        if not hits:
            return False, None
        qid = hits[0]["id"]
        req2 = urllib.request.Request(
            f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", headers=UA)
        with urllib.request.urlopen(req2, timeout=12) as r:
            ent = json.loads(r.read().decode())["entities"][qid]
        claims = ent.get("claims", {})
        emp = None
        for c in claims.get("P1128", []):  # employees
            try:
                emp = int(float(c["mainsnak"]["datavalue"]["value"]["amount"]))
            except Exception:
                pass
        return True, emp
    except Exception:
        return False, None


def tier_of(name: str, con=None, overrides: dict | None = None) -> str:
    n = (name or "").strip()
    # user watch-list pins (from Settings) win first, then curated config (A > B > C), word-aware
    if overrides:
        for co, tier in overrides.items():
            if _matches(co, n):
                return tier
    curated = _curated_tier(n)
    if curated:
        return curated
    # cache?
    if con is not None:
        cached = db.get_cached_tier(con, n)
        if cached:
            return cached
    found, emp = _wikidata_employees(n)
    if not found:
        tier = "U"
    elif emp is not None and emp >= config.WIKIDATA_MIN_EMPLOYEES_B:
        tier = "B"
    else:
        tier = "C"  # exists/notable but small-or-unknown size
    if con is not None:
        db.cache_tier(con, n, tier, via="wikidata")
    return tier


if __name__ == "__main__":
    for c in ["Razorpay", "Meesho", "Stripe", "Paytm", "HighRadius", "FamPay", " NovaPayXYZ "]:
        print(f"{c:14} -> {tier_of(c)}")
