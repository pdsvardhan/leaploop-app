"""Create/update the NPM proxy host for leaploop.vault7a.xyz -> authentik:9000 (SSO enforced on the
LAN path too, since the app has no auth of its own). Idempotent. Runs on the host (NPM API @ :81)."""
import json, re, urllib.request, urllib.error

NPM = "http://127.0.0.1:81/api"
env = open("/opt/homeserver/.env").read()
PW = re.search(r"^NPM_PASSWORD=(.*)$", env, re.M).group(1).strip().strip('"')
EMAIL = "pdsvardhan7@gmail.com"


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(NPM + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "{}")


st, tok = call("POST", "/tokens", {"identity": EMAIL, "secret": PW})
token = tok.get("token")
print("npm login st=", st, "token?", bool(token))
if not token:
    raise SystemExit("NPM login failed: " + str(tok)[:200])

st, hosts = call("GET", "/nginx/proxy-hosts", token=token)
exists = next((h for h in hosts if {"leaploop.vault7a.xyz", "leaploop.vault7a.xyz"} & set(h.get("domain_names", []))), None)
payload = {
    "domain_names": ["leaploop.vault7a.xyz"],
    "forward_scheme": "http", "forward_host": "authentik", "forward_port": 9000,
    "certificate_id": 2, "ssl_forced": True, "http2_support": True,
    "allow_websocket_upgrade": True, "block_exploits": True,
    "caching_enabled": False, "hsts_enabled": False, "access_list_id": 0,
    "advanced_config": "", "locations": [],
    "meta": {"letsencrypt_agree": False, "dns_challenge": False},
}
if exists:
    st, res = call("PUT", f"/nginx/proxy-hosts/{exists['id']}", payload, token)
    print("updated host id=", exists["id"], "st=", st, "| enabled=", res.get("enabled"))
else:
    st, res = call("POST", "/nginx/proxy-hosts", payload, token)
    print("created host id=", res.get("id"), "st=", st, "| err=", res.get("error"))
