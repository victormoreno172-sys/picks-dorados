"""Clasificación online (bloque 2): prepara Firebase con la cuenta de servicio (secreto FIREBASE_CUENTA).

- Crea (si no existe) la «app web» del proyecto y saca su configuración pública (apiKey y projectId) para
  meterla en la app al generarla. Esa configuración no es secreta (va en cualquier app web); lo que protege
  los datos son las reglas de Firestore, que también se publican desde aquí.
- Nada de esto se escribe en el repositorio: se guarda en la caché de GitHub Actions.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import requests

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "firebase_web.json")

REGLAS = """rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Cada jugador solo puede escribir su propia ficha; cualquiera con sesión puede leer las fichas (para el ranking)
    match /jugadores/{uid} {
      allow read: if request.auth != null;
      allow create, update: if request.auth != null && request.auth.uid == uid
        && request.resource.data.keys().hasOnly(['n', 'nl', 'p', 'reto', 'arc', 'nv', 't', 'pk'])
        && request.resource.data.n is string && request.resource.data.n.size() >= 3 && request.resource.data.n.size() <= 16;
      allow delete: if request.auth != null && request.auth.uid == uid;
      // Pronósticos: cada cambio es un documento nuevo con la hora del servidor; no se pueden cambiar ni borrar
      match /pk/{id} {
        allow read: if request.auth != null;
        allow create: if request.auth != null && request.auth.uid == uid && request.resource.data.ts == request.time
          && request.resource.data.keys().hasOnly(['k', 'd', 'j', 'sg', 'ts']) && request.resource.data.j is string && request.resource.data.j.size() < 400
          && request.resource.data.k is string && request.resource.data.k.size() < 320;
      }
    }
  }
}
"""


def _token():
    info = os.environ.get("FIREBASE_CUENTA")
    if not info:
        return None, None
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    k = json.loads(info)
    cr = service_account.Credentials.from_service_account_info(
        k, scopes=["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/firebase"])
    cr.refresh(Request())
    return cr.token, k["project_id"]


def _leer_cache() -> dict:
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guardar_cache(d: dict):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(d, f)


def _config_web(tok: str, proy: str) -> dict | None:
    H = {"Authorization": "Bearer " + tok}
    base = f"https://firebase.googleapis.com/v1beta1/projects/{proy}/webApps"
    apps = requests.get(base, headers=H, timeout=30).json().get("apps", [])
    if not apps:
        op = requests.post(base, headers=H, json={"displayName": "Partidos (web)"}, timeout=30).json()
        for _ in range(20):
            if op.get("done") or "name" not in op:
                break
            time.sleep(3)
            op = requests.get("https://firebase.googleapis.com/v1beta1/" + op["name"], headers=H, timeout=30).json()
        apps = requests.get(base, headers=H, timeout=30).json().get("apps", [])
    if not apps:
        return None
    c = requests.get(f"{base}/{apps[0]['appId']}/config", headers=H, timeout=30).json()
    return {"apiKey": c.get("apiKey"), "projectId": c.get("projectId") or proy} if c.get("apiKey") else None


def _publicar_reglas(tok: str, proy: str) -> bool:
    H = {"Authorization": "Bearer " + tok}
    rs = requests.post(f"https://firebaserules.googleapis.com/v1/projects/{proy}/rulesets", headers=H, timeout=30,
                       json={"source": {"files": [{"name": "firestore.rules", "content": REGLAS}]}})
    if not rs.ok:
        print(f"  online: no se pudieron crear las reglas ({rs.status_code}) {rs.text[:200]}")
        return False
    nombre = rs.json()["name"]
    rel = f"projects/{proy}/releases/cloud.firestore"
    r = requests.patch(f"https://firebaserules.googleapis.com/v1/{rel}", headers=H, timeout=30,
                       json={"release": {"name": rel, "rulesetName": nombre}})
    if r.status_code == 404:
        r = requests.post(f"https://firebaserules.googleapis.com/v1/projects/{proy}/releases", headers=H, timeout=30,
                          json={"name": rel, "rulesetName": nombre})
    print(f"  online: reglas de Firestore {'publicadas' if r.ok else 'puestas a mano en la consola (sin permiso para publicarlas desde aquí)'}")
    return r.ok or r.status_code == 403


def config_app() -> dict | None:
    """Configuración pública de Firebase para la app (o None si no se puede)."""
    c = _leer_cache()
    hreg = hashlib.sha1(REGLAS.encode()).hexdigest()[:10]
    if c.get("web") and c.get("reglas") == hreg and time.time() - c.get("t", 0) < 86400:
        return c["web"]
    try:
        tok, proy = _token()
        if not tok:
            return c.get("web")
        web = _config_web(tok, proy) or c.get("web")
        ok = _publicar_reglas(tok, proy) if c.get("reglas") != hreg else True
        _guardar_cache({"web": web, "reglas": hreg if ok else c.get("reglas"), "t": time.time()})
        print(f"  online: configuración web {'lista' if web else 'NO disponible'}")
        return web
    except Exception as e:  # noqa: BLE001
        print(f"  online: {type(e).__name__}: {e}")
        return c.get("web")
