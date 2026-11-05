"""Finalize Stage 3 in Ottomate AFTER the verifier APPROVEs: reconcile feature_claims,
set feature statuses, log the stage-3-complete event. Run on the server."""
import json, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:8110"
TOKEN = open("/opt/homeserver/ottomate/.token").read().strip()
SESSION = "stage3-build-2026-06-03"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=H)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


# 0) fix the public domain across project text fields (jobs -> leaploop)
st, proj = call("GET", "/api/projects/leaploop")
p = proj.get("project", proj)
patch = {"public_url": "https://leaploop.vault7a.xyz"}
for f in ("core_idea", "short_description", "problem_statement", "tagline"):
    if isinstance(p.get(f), str) and "jobs.vault7a.xyz" in p[f]:
        patch[f] = p[f].replace("jobs.vault7a.xyz", "leaploop.vault7a.xyz")
st, _ = call("PATCH", "/api/projects/leaploop", patch)
print(f"=== project domain fields -> leaploop ({list(patch.keys())}): {st}")

# 1) reconcile claims -> verified
ids = json.load(open("/tmp/claim_ids.json"))
print("=== reconcile claims ===")
for fid, cid in ids.items():
    if not cid:
        continue
    st, _ = call("PATCH", f"/api/feature-claims?id={cid}", {"reconciled_with": "verified"})
    print(f"  {fid} claim {cid}: {st}")

# 2) feature statuses
DONE = ["feat-tiering", "feat-linkedin-ingest", "feat-gmail-confirm", "feat-cleaner",
        "feat-rules-tailor", "feat-pdf-compile", "feat-triage-queue", "feat-apply-queue",
        "feat-manual-generate", "feat-tracker", "feat-settings", "feat-auth-deploy"]
print("=== feature statuses ===")
for fid in DONE:
    st, _ = call("PATCH", f"/api/projects/leaploop/features/{fid}", {"status": "done", "test_status": "passing"})
    print(f"  {fid} -> done/passing: {st}")
# Telegram stays partial (dormant until TELEGRAM_CHAT_ID)
st, _ = call("PATCH", "/api/projects/leaploop/features/feat-telegram-push",
             {"status": "building", "test_status": "not-tested"})
print(f"  feat-telegram-push -> building/not-tested (parked): {st}")

# 3) lifecycle -> shipped (deployed + live behind SSO)
st, _ = call("PATCH", "/api/projects/leaploop", {"lifecycle_phase": "shipped", "current_status": "shipped"})
print(f"=== lifecycle -> shipped: {st}")

# 4) stage-3-complete event
st, _ = call("POST", "/api/skill-events", {
    "project_slug": "leaploop", "event_type": "stage_3_complete", "session_id": SESSION,
    "evidence": {"commit": "a92f407", "deploy_url": "https://leaploop.vault7a.xyz",
                 "tests": "9/9 engine units pass", "verifier": "APPROVE",
                 "note": "GlitchTip deferred (dormant hook + logs); Telegram parked until chat_id"}})
print(f"=== skill-event stage_3_complete: {st}")
print("FINALIZED")
