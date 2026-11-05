"""Gmail-IMAP: (1) auto-confirm 'applied' from confirmation emails; (2) ingest LinkedIn job-alert emails.
Reads GMAIL_USER + GMAIL_APP_PASSWORD from secrets.env (or env). Read-only on the mailbox.

IMAP budget (iter-141): Gmail throttles chatty clients and answers with "System Error" or
drops the socket (EOF). The old scan pulled up to 200 message headers one FETCH at a time,
every 30 minutes — ~9,600 round-trips a day — and opened a second connection for the
LinkedIn ingest. Both legs now narrow server-side and fetch in ONE batched round-trip, and
a cycle shares a single connection.
"""
from __future__ import annotations
import email, html, imaplib, os, re, time
from email.header import decode_header

try:
    from . import db as _db
except ImportError:  # running as a script
    import db as _db

SECRETS = os.environ.get("LEAPLOOP_SECRETS", "/opt/homeserver/leaploop/secrets.env")

# Guardrails so one pathological mailbox can never restore the old hammer-the-server pattern.
MAX_CONFIRM_MSGS = 60      # headers pulled per cycle for confirmation scanning
MAX_LINKEDIN_MSGS = 25     # full bodies pulled per cycle for alert parsing
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0
MAX_RECONNECTS = 3         # per Session — one dropped socket is normal, a stream of them is not


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)            # &middot; -> ·, &amp; -> &, &nbsp; -> \xa0, &#160; -> ...
    return re.sub(r"\s+", " ", s).strip()

CONFIRM_PATTERNS = [
    "thank you for applying", "thanks for applying", "application was sent",
    "application received", "we received your application", "successfully submitted",
    "your application to", "application has been submitted",
]

TRANSIENT_IMAP_ERRORS = (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError)

# Errors that will never clear by waiting. Retrying a rejected app password three times only
# spent 10.8s and sent Gmail three more bad logins (measured 2026-09-04, to-do #423).
FATAL_IMAP_MARKERS = ("authenticationfailed", "invalid credentials",
                      "application-specific password", "web login required")


def is_fatal_imap(e) -> bool:
    s = str(e).lower()
    return any(t in s for t in FATAL_IMAP_MARKERS)


def _secrets() -> dict:
    d = {}
    try:
        for line in open(SECRETS, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD"):
        if os.environ.get(k):
            d[k] = os.environ[k]
    return d


def connect():
    s = _secrets()
    user, pw = s.get("GMAIL_USER"), s.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        raise RuntimeError("missing GMAIL_USER / GMAIL_APP_PASSWORD")
    m = imaplib.IMAP4_SSL("imap.gmail.com")
    m.login(user, pw)
    return m


def with_retry(fn, attempts: int = RETRY_ATTEMPTS, base_delay: float = RETRY_BASE_DELAY):
    """Retry a transient IMAP failure with exponential backoff. Gmail's 'System Error' and
    socket EOF are both throttling symptoms that clear on a short pause.

    Only correct for calls that build their own connection (i.e. `connect`). Work on an
    EXISTING connection belongs in Session.call — see the class docstring.
    """
    last = None
    for i in range(attempts):
        try:
            return fn()
        except TRANSIENT_IMAP_ERRORS as e:
            if is_fatal_imap(e):
                raise
            last = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
    raise last


class Session:
    """A Gmail-IMAP connection that heals itself once after a dead-socket abort.

    imaplib raises IMAP4.abort when the server drops the socket, and the connection is unusable
    from that moment. with_retry did not know that: it re-ran the same operation on the same
    dead connection, so all three attempts were guaranteed to fail and the only thing the retry
    achieved was ~6s of backoff before the leg gave up. A Session reconnects once and re-runs
    the operation on the fresh connection; a second abort is a real failure and propagates.
    """

    def __init__(self, m=None):
        self.m = m if m is not None else with_retry(connect)
        self.reconnects = 0
        self._mailbox = None

    def select(self, mailbox: str = "INBOX"):
        self._mailbox = mailbox
        return self.call(lambda m: m.select(mailbox))

    def _reconnect(self):
        close_quietly(self.m)
        # with_retry, not a bare connect: a transient failure DURING the reconnect used to
        # propagate immediately instead of backing off once.
        self.m = with_retry(connect)
        self.reconnects += 1
        if self._mailbox:
            self.m.select(self._mailbox)

    def call(self, fn, attempts: int = RETRY_ATTEMPTS, base_delay: float = RETRY_BASE_DELAY):
        """Run fn(connection); retry transient failures, reconnect once on a dead socket.

        The budget is one reconnect per operation, capped at MAX_RECONNECTS for the whole
        session. A session-wide budget of one meant a cycle that healed in its first minute
        was defenceless ten minutes later; an uncapped budget could loop reconnecting.
        """
        last, reconnected_here = None, False
        for i in range(attempts):
            try:
                return fn(self.m)
            except imaplib.IMAP4.abort as e:
                last = e
                if reconnected_here or self.reconnects >= MAX_RECONNECTS:
                    raise
                reconnected_here = True
                self._reconnect()
            except TRANSIENT_IMAP_ERRORS as e:
                if is_fatal_imap(e):
                    raise
                last = e
                if i < attempts - 1:
                    time.sleep(base_delay * (2 ** i))
        raise last


def close_quietly(m) -> None:
    """Log out without letting a teardown error mask the real result. Takes a Session or a
    raw imaplib connection."""
    if m is None:
        return
    m = getattr(m, "m", m)
    try:
        m.logout()
    except Exception:
        pass


def _decode(s):
    if not s:
        return ""
    parts = decode_header(s)
    return "".join((b.decode(enc or "utf-8", "replace") if isinstance(b, bytes) else b) for b, enc in parts)


def _search(m, criteria: str) -> list[bytes]:
    """One IMAP SEARCH -> list of message numbers (may be empty)."""
    typ, data = m.search(None, criteria)
    if typ != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def _fetch_batch(m, nums: list[bytes], spec: str) -> list[bytes]:
    """Fetch many messages in ONE round-trip.

    The old code issued one FETCH per message; that is what tripped Gmail's throttle.
    imaplib accepts a comma-joined sequence set, and the response interleaves literals with
    their envelope lines — we keep only the literal payloads.
    """
    if not nums:
        return []
    seq = b",".join(nums).decode("ascii")
    typ, data = m.fetch(seq, spec)
    if typ != "OK" or not data:
        return []
    return [part[1] for part in data if isinstance(part, tuple) and len(part) > 1 and part[1]]


def scan_confirmations(con=None, days: int = 3, m=None):
    """Find recent 'application received' emails; return [(company_guess, subject)]. Pure read —
    no DB writes (sync_applied records the real company+title when it flips a picked role).

    Narrows server-side by SUBJECT so we pull a handful of headers, not the whole mailbox.
    Pass `m` to share a connection with the rest of the cycle.
    """
    own = m is None
    sess = m if isinstance(m, Session) else Session(m)
    try:
        sess.select("INBOX")
        since = _since(days)
        nums: list[bytes] = []
        seen_nums: set[bytes] = set()
        for pat in CONFIRM_PATTERNS:
            for n in sess.call(lambda mm, p=pat: _search(mm, f'(SINCE {since} SUBJECT "{p}")')):
                if n not in seen_nums:
                    seen_nums.add(n)
                    nums.append(n)
        nums = nums[-MAX_CONFIRM_MSGS:]
        blobs = sess.call(lambda mm: _fetch_batch(
            mm, nums, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])"))
        found = []
        for blob in blobs:
            hdr = email.message_from_bytes(blob)
            subj = _decode(hdr.get("Subject", "")).lower()
            frm = _decode(hdr.get("From", ""))
            if any(p in subj for p in CONFIRM_PATTERNS):
                found.append((_company_from(frm, subj), subj[:80]))
        return found
    finally:
        if own:
            close_quietly(sess)


def sync_applied(con, days: int = 3, m=None) -> dict:
    """Auto-confirm loop: scan 'application received' emails, flip the matching role to applied,
    and record it in applied_index for dedupe. One role per confirmation (the most likely just-applied).
    Returns {'matched': emails, 'flipped': roles, 'companies': [...]}. Read-only on the mailbox."""
    confirmations = scan_confirmations(con, days=days, m=m)   # pure read; this fn writes applied_index below
    flipped, companies, seen = 0, [], set()
    for company, _subj in confirmations:
        if not company:
            continue
        for role in _db.find_active_by_company(con, company):
            if role["source_id"] in seen:
                continue
            _db.mark_applied(con, role["source_id"], True)
            _db.add_applied(con, role["company"], role["title"],
                            resume=role.get("pdf_path") or "", source="gmail-confirm")
            seen.add(role["source_id"])
            flipped += 1
            companies.append(role["company"])
            break   # one confirmation marks one role
    return {"matched": len(confirmations), "flipped": flipped, "companies": companies}


# LinkedIn job-alert link: capture the URL and the anchor's inner text (the job title).
_LI_JOB_RE = re.compile(
    r'<a\b[^>]*href="(https://www\.linkedin\.com/(?:comm/)?jobs/view/[^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)


def _company_after(html_tail: str) -> str:
    """First text chunk after a job link in a LinkedIn alert is usually 'Company · Location'."""
    txt = _strip_tags(html_tail)
    if not txt:
        return ""
    head = re.split(r"[·•|\-–—]", txt)[0].strip()   # company is before the middot/bullet
    head = re.sub(r"\b(is hiring|hiring|posted|new|jobs?)\b.*$", "", head, flags=re.I).strip()
    return head[:48] if 1 < len(head) <= 60 else ""


def parse_linkedin_html(html: str) -> list[dict]:
    """Pure parse of a LinkedIn job-alert email's HTML -> role dicts. Unit-testable (no IMAP).

    jd_text is deliberately empty: a LinkedIn alert carries no job description, and fetching
    the job page would collide with the locked no-scraping rail. LinkedIn roles are a
    discovery signal only (iter-141, item 886).
    """
    roles, seen = [], set()
    for m in _LI_JOB_RE.finditer(html or ""):
        url = m.group(1).split("?")[0]
        title = _strip_tags(m.group(2))
        if not title or len(title) > 120 or title.lower() in ("view job", "see job", "apply"):
            continue
        job_id = re.search(r"/jobs/view/(\d+)", url)
        sid = "li:" + (job_id.group(1) if job_id else re.sub(r"\W+", "", url)[-18:])
        if sid in seen:
            continue
        seen.add(sid)
        company = _company_after(html[m.end():m.end() + 600])
        roles.append({"source_id": sid, "company": company, "title": title,
                      "location": "India", "mode": "", "url": url, "source": "LinkedIn",
                      "jd_text": "", "posted": ""})
    return roles


def ingest_linkedin(days: int = 2, m=None):
    """Parse LinkedIn job-alert emails -> [{company,title,url,source,...}]. Daily backstop source.
    Best-effort: title from the link text, company from the following 'Company · Location' text.

    Pass `m` to share the cycle's connection. Bodies are fetched in one batched round-trip.
    """
    own = m is None
    sess = m if isinstance(m, Session) else Session(m)
    try:
        sess.select("INBOX")
        nums = sess.call(lambda mm: _search(
            mm, f'(FROM "jobalerts-noreply@linkedin.com" SINCE {_since(days)})'))
        nums = nums[-MAX_LINKEDIN_MSGS:]
        roles = []
        for blob in sess.call(lambda mm: _fetch_batch(mm, nums, "(RFC822)")):
            msg = email.message_from_bytes(blob)
            body = ""
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode("utf-8", "replace")
            roles += parse_linkedin_html(body)
        # de-dupe by source_id across all emails in the window
        uniq = {r["source_id"]: r for r in roles}
        return list(uniq.values())
    finally:
        if own:
            close_quietly(sess)


def _since(days):
    import datetime
    return (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")


def _company_from(frm, subj):
    # Prefer the company named in the subject (e.g. "your application was sent to Navi").
    m = re.search(r"(?:application (?:was )?(?:sent|submitted)\s+to|applying (?:to|at)|"
                  r"your application to|application to|application for .* at)\s+([A-Za-z0-9&.\-' ]{2,40})",
                  subj, re.I)
    if m:
        return m.group(1).strip(" .-'").title()
    m2 = re.search(r"@([a-z0-9-]+)\.", (frm or "").lower())
    return m2.group(1).title() if m2 else ""


if __name__ == "__main__":
    import sys
    try:
        if "--linkedin" in sys.argv:
            r = ingest_linkedin()
            print(f"linkedin alert roles: {len(r)}")
            for x in r[:12]:
                print(f"  {(x['company'] or '?'):20} {x['title'][:48]:48} {x['url']}")
        else:
            c = scan_confirmations()
            print(f"confirmation emails matched: {len(c)}")
            for co, s in c[:10]:
                print(f"  {co:18} {s}")
    except Exception as e:
        print("IMAP error:", e)
