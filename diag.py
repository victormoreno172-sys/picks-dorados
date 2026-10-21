"""Diagnóstico temporal: qué puede hacer la cuenta de servicio de Firebase (sin publicar ninguna clave)."""
import json, os, requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
k = json.loads(os.environ["FIREBASE_CUENTA"]); P = k["project_id"]
cr = service_account.Credentials.from_service_account_info(k, scopes=["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/firebase"])
cr.refresh(Request()); H = {"Authorization": "Bearer " + cr.token}
out = {"proyecto": P, "cuenta": k.get("client_email", "").split("@")[0]}
def g(n, url, **kw):
    try:
        r = requests.get(url, headers=H, timeout=30, **kw); out[n] = {"st": r.status_code, "txt": r.text[:300] if r.status_code != 200 else None}
        return r.json() if r.status_code == 200 else None
    except Exception as e: out[n] = str(e)
w = g("webApps", f"https://firebase.googleapis.com/v1beta1/projects/{P}/webApps")
if w is not None: out["webApps_n"] = len(w.get("apps", []))
a = g("androidApps", f"https://firebase.googleapis.com/v1beta1/projects/{P}/androidApps")
if a is not None: out["androidApps_n"] = len(a.get("apps", []))
d = g("firestore", f"https://firestore.googleapis.com/v1/projects/{P}/databases")
if d is not None: out["firestore_dbs"] = [(x.get("name", "").split("/")[-1], x.get("locationId"), x.get("type")) for x in d.get("databases", [])]
c = g("authConfig", f"https://identitytoolkit.googleapis.com/admin/v2/projects/{P}/config")
if c is not None: out["auth"] = {"email": (c.get("signIn") or {}).get("email"), "anon": (c.get("signIn") or {}).get("anonymous")}
rr = g("rules", f"https://firebaserules.googleapis.com/v1/projects/{P}/releases")
if rr is not None: out["rules_releases"] = [x.get("name", "").split("/")[-1] for x in rr.get("releases", [])]
g("services", f"https://serviceusage.googleapis.com/v1/projects/{P}/services?filter=state:ENABLED&pageSize=200")
try:
    r = requests.get(f"https://serviceusage.googleapis.com/v1/projects/{P}/services?filter=state:ENABLED&pageSize=200", headers=H, timeout=30)
    if r.ok: out["apis"] = [s["config"]["name"] for s in r.json().get("services", [])]
except Exception: pass
json.dump(out, open("resultado.json", "w"), ensure_ascii=False, indent=1)
