"""Mantenimiento del ranking online (Firestore «jugadores») con la cuenta de servicio FIREBASE_CUENTA.
python jugadores.py            -> lista las cuentas (uid, nombre, última actividad)
python jugadores.py UID [UID…]  -> borra esas cuentas
"""
import json
import sys
from datetime import datetime, timezone

import requests

from online import _token

tok, proy = _token()
if not tok:
    sys.exit("Falta FIREBASE_CUENTA")
H = {"Authorization": "Bearer " + tok}
BASE = f"https://firestore.googleapis.com/v1/projects/{proy}/databases/(default)/documents/jugadores"

if sys.argv[1:2] == ["reglas"]:   # python jugadores.py reglas -> qué reglas tiene Firestore ahora
    rel = requests.get(f"https://firebaserules.googleapis.com/v1/projects/{proy}/releases/cloud.firestore", headers=H, timeout=30).json()
    src = requests.get(f"https://firebaserules.googleapis.com/v1/{rel.get('rulesetName')}", headers=H, timeout=30).json()
    txt = "".join(f.get("content", "") for f in src.get("source", {}).get("files", []))
    print("::notice::" + ("con pk" if "'pk'" in txt else "SIN pk") + " · " + rel.get("updateTime", ""))
    sys.exit()
if sys.argv[1:2] == ["ver"]:   # python jugadores.py ver UID -> muestra lo que tiene guardado
    for uid in sys.argv[2:]:
        f = requests.get(f"{BASE}/{uid}", headers=H, timeout=30).json().get("fields", {})
        for k in ("n", "t", "reto", "arc"):
            print("::notice::" + k + " = " + json.dumps(f.get(k), ensure_ascii=False)[:900])
    sys.exit()
if sys.argv[1:]:
    for uid in sys.argv[1:]:
        r = requests.delete(f"{BASE}/{uid}", headers=H, timeout=30)
        print("::notice::" + ("borrado " if r.ok else f"error {r.status_code} ") + uid)
    sys.exit()

docs, pt = [], ""
while True:
    j = requests.get(BASE, headers=H, params={"pageSize": 300, **({"pageToken": pt} if pt else {})}, timeout=30).json()
    docs += j.get("documents", []); pt = j.get("nextPageToken", "")
    if not pt:
        break
filas = []
for d in docs:
    f = d.get("fields", {})
    n = (f.get("n") or {}).get("stringValue", "")
    t = int((f.get("t") or {}).get("integerValue", 0) or (f.get("t") or {}).get("doubleValue", 0) or 0)
    filas.append((n.lower(), n, d["name"].split("/")[-1], t, d.get("updateTime", "")))
for _, n, uid, t, up in sorted(filas):
    act = datetime.fromtimestamp(t / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M") if t else "-"
    print(f"::notice::JUG | {n!r:24} | {uid} | t={act} UTC | doc={up[:16]}")
print("total", len(filas))
