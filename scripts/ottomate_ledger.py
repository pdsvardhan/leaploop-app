"""Post the Stage-3 ledger to Ottomate: feature_claims + test_run + deploy_artifact.
Runs on the server (Ottomate API @ 127.0.0.1:8110). Token from /opt/homeserver/ottomate/.token.
Prints claim IDs (for later reconcile). Idempotent-ish: re-running adds new claim rows (fine)."""
import json, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:8110"
TOKEN = open("/opt/homeserver/ottomate/.token").read().strip()
SESSION = "stage3-build-2026-06-03"
SHA = "a92f407"
NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode()[:200])


CLAIMS = {
    "feat-tiering": "A/B/C/U tiering: word-aware curated match + curated Tier-C (Paytm->C) before keyless Wikidata; no loose-substring false positives.",
    "feat-linkedin-ingest": "LinkedIn alert-email ingest parses company+title+url (30 real roles), wired into the cycle as a backstop.",
    "feat-gmail-confirm": "Gmail auto-confirm wired into the applied loop: confirmation email flips a picked role to applied; manual override via /applied.",
    "feat-cleaner": "India-PM filter + dedupe + drop-applied + muted-company, honoring editable settings; verified 1065->~91.",
    "feat-rules-tailor": "Rules engine selects cluster by JD keyword overlap (fintech JD->fintech_payments), safe-default fallback; per-JD .tex.",
    "feat-pdf-compile": "tectonic compiles per-JD .tex to the constant-named PDF Sai_Vardhan_Palli_Product_Manager_IIMB_CV.pdf (94KB verified).",
    "feat-triage-queue": "Triage screen: role cards yes/no/snooze + mute + Preview JD, Tier-A filter, tier/fit/age sort; wired to /api/roles + /decision.",
    "feat-apply-queue": "Apply screen: real PDF preview, swap-variant (re-tailor), copy referral (locked verbatim template), applied toggle.",
    "feat-manual-generate": "Generate screen: paste JD text or role URL -> tailored PDF via /api/generate (text+URL only, no OCR/upload).",
    "feat-tracker": "Tracker screen: searchable applied list (company/role/resume/date/source/status) + CSV export; 49 applied rows.",
    "feat-settings": "Settings screen: edit role types/levels/exclude + watch-list tiers, persisted via /api/settings; cleaner honors on next poll.",
    "feat-auth-deploy": "Dockerized cockpit on :8509 behind Authentik SSO at leaploop.vault7a.xyz (NPM + Cloudflare tunnel); cron watcher; anon access blocked.",
}

print("=== feature_claims ===")
ids = {}
for fid, text in CLAIMS.items():
    st, res = post("/api/feature-claims", {"feature_id": fid, "claim_text": text,
                                           "source": "coder-agent", "claimed_by_session": SESSION, "claimed_at": NOW})
    cid = res.get("id") if isinstance(res, dict) else None
    ids[fid] = cid
    print(f"  {fid}: st={st} id={cid}" + (f" err={res}" if st >= 300 else ""))

print("=== test_run ===")
st, tr = post("/api/test-runs", {"project_slug": "leaploop", "commit_sha": SHA, "branch": "master",
                                 "started_at": NOW, "completed_at": NOW, "result": "passed",
                                 "total": 9, "passed": 9, "failed": 0, "skipped": 0, "triggered_by": "manual"})
tr_id = tr.get("id") if isinstance(tr, dict) else None
print(f"  test_run: st={st} id={tr_id}" + (f" err={tr}" if st >= 300 else ""))

print("=== deploy_artifact ===")
st, da = post("/api/deploy-artifacts", {"project_slug": "leaploop", "feature_ids": list(CLAIMS.keys()),
                                        "commit_sha": SHA, "deploy_url": "https://leaploop.vault7a.xyz",
                                        "deployed_by_session": SESSION, "smoke_test_passed": True,
                                        "smoke_test_run_id": tr_id,
                                        "notes": "Docker :8509 behind Authentik SSO; SSO gate verified (anon->login); browser-smoked all 7 screens."})
print(f"  deploy_artifact: st={st}" + (f" id={da.get('id')}" if isinstance(da, dict) else f" err={da}"))

open("/tmp/claim_ids.json", "w").write(json.dumps(ids))
print("claim ids saved to /tmp/claim_ids.json")
