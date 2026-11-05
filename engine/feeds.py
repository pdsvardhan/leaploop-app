"""ATS feed registry + fetchers. Verified live 2026-06-02 (Task A).
Public ATS JSON only (no auth, no scraping). Returns normalized role dicts:
  {source_id, company, title, location, url, source, jd_text, posted}
"""
from __future__ import annotations
import json, re, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (LeapLoop/1.0; personal job radar)"}

# Verified-working feeds (Task A 2026-06-02). india_pm_now = live count at verification.
FEEDS = {
    "phonepe":    {"ats": "greenhouse", "url": "https://boards-api.greenhouse.io/v1/boards/phonepe/jobs?content=true"},
    "meesho":     {"ats": "lever",      "url": "https://api.lever.co/v0/postings/meesho?mode=json"},
    "paytm":      {"ats": "lever",      "url": "https://api.lever.co/v0/postings/paytm?mode=json"},
    "stripe":     {"ats": "greenhouse", "url": "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true"},
    "amazon":     {"ats": "amazon",     "url": "https://www.amazon.jobs/en/search.json?base_query=product%20manager&country=IND&result_limit=100"},
    "highradius": {"ats": "greenhouse", "url": "https://boards-api.greenhouse.io/v1/boards/highradius/jobs?content=true"},
    "mindtickle": {"ats": "lever",      "url": "https://api.lever.co/v0/postings/mindtickle?mode=json"},
    "fampay":     {"ats": "lever",      "url": "https://api.lever.co/v0/postings/fampay?mode=json"},
    "hackerrank": {"ats": "greenhouse", "url": "https://boards-api.greenhouse.io/v1/boards/hackerrank/jobs?content=true"},
    "groww":      {"ats": "greenhouse", "url": "https://boards-api.greenhouse.io/v1/boards/groww/jobs?content=true"},
    "cred":       {"ats": "lever",      "url": "https://api.lever.co/v0/postings/cred?mode=json"},
    "epifi":      {"ats": "lever",      "url": "https://api.lever.co/v0/postings/epifi?mode=json"},
    # Added 2026-06-24 (iter-1): probed live, public ATS JSON, no auth/scraping.
    "postman":    {"ats": "greenhouse", "url": "https://boards-api.greenhouse.io/v1/boards/postman/jobs?content=true"},
    "slice":      {"ats": "greenhouse", "url": "https://boards-api.greenhouse.io/v1/boards/slice/jobs?content=true"},
    "observeai":  {"ats": "greenhouse", "url": "https://boards-api.greenhouse.io/v1/boards/observeai/jobs?content=true"},
    "navi":       {"ats": "ashby",      "url": "https://api.ashbyhq.com/posting-api/job-board/navi"},
    "atlan":      {"ats": "ashby",      "url": "https://api.ashbyhq.com/posting-api/job-board/atlan"},
    "stable":     {"ats": "ashby",      "url": "https://api.ashbyhq.com/posting-api/job-board/stable"},
}

# Watch-list companies NOT on a public feed (Workday/iCIMS/SuccessFactors/bespoke) -> LinkedIn-email backstop.
LINKEDIN_BACKSTOP = [
    "Mastercard", "American Express", "IDFC FIRST Bank", "JPMorgan Chase", "HDFC", "Goldman Sachs",
    "Aditya Birla Capital", "Citi", "Barclays", "Standard Chartered", "Walmart Global Tech", "Google",
    "Microsoft", "CarTrade/OLX", "Razorpay", "Policybazaar", "Lenskart", "Cult.fit", "Flipkart",
    "Swiggy", "Zomato", "Uber", "Adobe", "Atlassian", "Salesforce",
]


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&[a-z]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _greenhouse(company, url):
    out = []
    for j in _get(url).get("jobs", []):
        out.append({
            "source_id": f"gh:{company}:{j.get('id')}", "company": company.title(),
            "title": j.get("title", ""), "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""), "source": "ATS",
            "jd_text": _strip_html(j.get("content", "")), "posted": j.get("updated_at", ""),
        })
    return out


def _lever(company, url):
    out = []
    for j in _get(url):
        cats = j.get("categories", {}) or {}
        out.append({
            "source_id": f"lv:{company}:{j.get('id')}", "company": company.title(),
            "title": j.get("text", ""), "location": cats.get("location", ""),
            "url": j.get("hostedUrl", ""), "source": "ATS",
            "jd_text": _strip_html(j.get("descriptionPlain") or j.get("description", "")),
            "posted": str(j.get("createdAt", "")),
        })
    return out


def _amazon(company, url):
    out = []
    for j in _get(url).get("jobs", []):
        out.append({
            "source_id": f"az:{j.get('id_icims') or j.get('id')}", "company": "Amazon",
            "title": j.get("title", ""), "location": j.get("normalized_location", ""),
            "url": "https://www.amazon.jobs" + (j.get("job_path", "")), "source": "ATS",
            "jd_text": _strip_html((j.get("description_short", "") or "") + " " + (j.get("basic_qualifications", "") or "")),
            "posted": j.get("posted_date", ""),
        })
    return out


def _ashby(company, url):
    out = []
    for j in _get(url).get("jobs", []):
        if j.get("isListed") is False:        # skip unlisted/internal postings
            continue
        out.append({
            "source_id": f"ash:{company}:{j.get('id')}", "company": company.title(),
            "title": j.get("title", ""), "location": j.get("location") or "",
            "url": j.get("jobUrl") or j.get("applyUrl", ""), "source": "ATS",
            "jd_text": _strip_html(j.get("descriptionPlain") or j.get("descriptionHtml", "")),
            "posted": str(j.get("publishedAt", "")),
        })
    return out


_FETCHERS = {"greenhouse": _greenhouse, "lever": _lever, "amazon": _amazon, "ashby": _ashby}


def fetch_all(feeds=FEEDS):
    """Fetch every feed. Returns (roles, health) where health[company] = {ok,count,err,last}."""
    roles, health = [], {}
    for co, meta in feeds.items():
        fn = _FETCHERS.get(meta["ats"])
        try:
            r = fn(co, meta["url"]) if fn else []
            roles += r
            health[co] = {"ok": True, "count": len(r), "err": None, "last": time.time()}
        except Exception as e:
            health[co] = {"ok": False, "count": 0, "err": str(e)[:180], "last": time.time()}
    return roles, health


if __name__ == "__main__":
    roles, health = fetch_all()
    print(f"fetched {len(roles)} roles from {len(FEEDS)} feeds")
    for co, h in health.items():
        print(f"  {'OK ' if h['ok'] else 'ERR'} {co:12} {h['count']:3} {h.get('err') or ''}")
