"""Limpieza temporal: fichas repetidas con el mismo nombre (se queda la más reciente). No publica claves."""
import json, os, online, requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
k = json.loads(os.environ["FIREBASE_CUENTA"]); P = k["project_id"]
cr = service_account.Credentials.from_service_account_info(k, scopes=["https://www.googleapis.com/auth/datastore", "https://www.googleapis.com/auth/cloud-platform"]); cr.refresh(Request())
H = {"Authorization": "Bearer " + cr.token}; B = f"https://firestore.googleapis.com/v1/projects/{P}/databases/(default)/documents"
docs = requests.get(f"{B}/jugadores?pageSize=300", headers=H, timeout=30).json().get("documents", [])
f = lambda d, c: (d.get("fields", {}).get(c) or {})
fichas = [(d["name"], (f(d, "nl").get("stringValue") or ""), int(f(d, "t").get("integerValue") or 0)) for d in docs]
out = {"antes": [(n.split("/")[-1][:6], nl, t) for n, nl, t in fichas], "borradas": []}
por = {}
for n, nl, t in fichas: por.setdefault(nl, []).append((t, n))
for nl, l in por.items():
    for t, n in sorted(l, reverse=True)[1:]:
        r = requests.delete(f"https://firestore.googleapis.com/v1/{n}", headers=H, timeout=30); out["borradas"].append((nl, n.split("/")[-1][:6], r.status_code))
json.dump(out, open("resultado.json", "w"), ensure_ascii=False, indent=1)
