"""Configure Authentik for LeapLoop: proxy provider + application + embedded-outpost binding.
Idempotent. Runs INSIDE the leaploop container (reaches authentik:9000 + leaploop:8509 on
authentik-net). Token passed via env TK. Clones the established SSO pattern (mode=proxy)."""
import json, os, urllib.request, urllib.error

BASE = "http://authentik:9000/api/v3"
TK = os.environ["TK"]
# Public Authentik resource IDs (visible in the admin UI, shared across all vault7a SSO apps) —
# NOT secrets. The API bearer token is the only secret and is passed in via env TK at runtime.
AUTHZ_FLOW = "4a34fcb9-17d8-42c1-9fc5-2b8b9113fa5a"      # gitleaks:allow
INVALID_FLOW = "c6d3d162-7bef-437e-a502-8c321888fe64"    # gitleaks:allow
OUTPOST = "c37abe61-5500-4925-9107-cea4cb47d647"         # gitleaks:allow


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {TK}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "{}")


# 0) reachability: can this container serve, and (implicitly) can authentik reach us by name
try:
    with urllib.request.urlopen("http://leaploop:8509/api/healthz", timeout=5) as r:
        print("reachable http://leaploop:8509 ->", r.read().decode()[:60])
except Exception as e:
    print("WARN reachability:", e)

# 1) proxy provider (idempotent by name)
_, plist = call("GET", "/providers/proxy/?search=leaploop-proxy")
prov = next((p for p in plist.get("results", []) if p["name"] == "leaploop-proxy"), None)
payload = {
    "name": "leaploop-proxy", "mode": "proxy",
    "external_host": "https://leaploop.vault7a.xyz",
    "internal_host": "http://leaploop:8509",
    "internal_host_ssl_validation": False,
    "authorization_flow": AUTHZ_FLOW, "invalidation_flow": INVALID_FLOW,
    "cookie_domain": "vault7a.xyz", "access_token_validity": "hours=24",
}
if prov:
    st, prov = call("PATCH", f"/providers/proxy/{prov['pk']}/", payload)
    print("provider updated pk=", prov.get("pk"), "st=", st)
else:
    st, prov = call("POST", "/providers/proxy/", payload)
    print("provider created pk=", prov.get("pk"), "st=", st)
PK = prov.get("pk")
if not PK:
    print("ERROR provider:", prov); raise SystemExit(1)

# 2) application (idempotent by slug)
_, alist = call("GET", "/core/applications/?search=leaploop")
app = next((a for a in alist.get("results", []) if a["slug"] == "leaploop"), None)
app_payload = {"name": "LeapLoop", "slug": "leaploop", "provider": PK,
               "meta_launch_url": "https://leaploop.vault7a.xyz",
               "meta_description": "Private PM job-hunt cockpit", "open_in_new_tab": False}
if app:
    st, app = call("PATCH", f"/core/applications/{app['slug']}/", app_payload)
    print("application updated slug=", app.get("slug"), "st=", st)
else:
    st, app = call("POST", "/core/applications/", app_payload)
    print("application created slug=", app.get("slug"), "st=", st)

# 3) bind provider to the embedded outpost
_, op = call("GET", f"/outposts/instances/{OUTPOST}/")
provs = sorted(set(op.get("providers", []) + [PK]))
st, op2 = call("PATCH", f"/outposts/instances/{OUTPOST}/", {"providers": provs})
print("outpost providers now:", op2.get("providers"), "st=", st)
print("DONE")
