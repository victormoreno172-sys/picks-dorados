"""
Notificaciones al móvil (app Android) con Firebase Cloud Messaging.

La app se apunta a "temas": uno por cada partido, competición o juego con ☆ (y por tipo de aviso:
i = empieza, g = goles/sets/mapas, f = final), uno por cada apuesta del bot (ab_...) y "bot" para el
aviso diario. Aquí solo se manda el mensaje al tema; Firebase lo entrega a los móviles apuntados.

El nombre del tema es un resumen (hash) del texto, el mismo que calcula la app (hashTema en
plantilla.html): así no hace falta guardar en ningún sitio qué sigue cada móvil.

La clave de la cuenta de servicio de Firebase va en el secreto FIREBASE_CUENTA.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata

import requests

_TOKEN = {"v": None, "hasta": 0.0, "proyecto": None}


def _b36(n: int) -> str:
    dig = "0123456789abcdefghijklmnopqrstuvwxyz"
    s = ""
    while True:
        n, r = divmod(n, 36)
        s = dig[r] + s
        if not n:
            return s


def tema(txt: str) -> str:
    """Igual que hashTema() de la app: NFKD, sin tildes, minúsculas y djb2 en base 36."""
    s = unicodedata.normalize("NFKD", str(txt))
    s = "".join(c for c in s if not ("̀" <= c <= "ͯ")).lower()
    h = 5381
    for c in s:
        h = (h * 33 + ord(c)) & 0xFFFFFFFF
    return _b36(h)


def liga_base(liga: str) -> str:
    return re.sub(r" · Bo\d+$", "", liga or "", flags=re.I)


def temas_partido(tipo: str, fecha: str, local: str, visitante: str, liga: str, dep: str) -> list[str]:
    """Temas a los que avisar de algo de este partido (partido ☆, competición ☆ y juego ☆)."""
    out = [f"{tipo}_{tema(f'p:{local}|{visitante}')}", f"{tipo}_{tema('l:' + liga_base(liga))}"]
    if dep == "e":
        juego = (liga or "").split(" · ")[0].strip()
        if juego:
            out.append(f"{tipo}_{tema('j:' + juego)}")
    return out


def tema_apuesta(clave: str) -> str:
    return "ab_" + tema("a:" + clave)


def clave_apuesta(a: dict) -> str:
    """Igual que claveApBot() de la app."""
    return "|".join([a.get("fecha", ""), a.get("tipo", ""), "+".join(f"{p.get('local')}>{p.get('mercado')}" for p in a.get("piernas", []))])


def disponible() -> bool:
    return bool(os.environ.get("FIREBASE_CUENTA"))


def _token() -> str | None:
    if _TOKEN["v"] and time.time() < _TOKEN["hasta"] - 60:
        return _TOKEN["v"]
    info = os.environ.get("FIREBASE_CUENTA")
    if not info:
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        k = json.loads(info)
        cr = service_account.Credentials.from_service_account_info(
            k, scopes=["https://www.googleapis.com/auth/firebase.messaging"])
        cr.refresh(Request())
        _TOKEN.update(v=cr.token, hasta=time.time() + 3000, proyecto=k["project_id"])
        return cr.token
    except Exception as e:  # noqa: BLE001
        print(f"  aviso notificaciones: no hay token ({type(e).__name__}: {e})")
        return None


def enviar(temas: list[str], titulo: str, cuerpo: str, datos: dict | None = None, etiqueta: str = "") -> bool:
    """Manda un aviso a los móviles apuntados a cualquiera de los temas (como mucho 5 por mensaje)."""
    tk = _token()
    if not tk or not temas:
        return False
    temas = list(dict.fromkeys(temas))[:5]
    msg = {"notification": {"title": titulo[:120], "body": cuerpo[:240]},
           "data": {k: str(v) for k, v in (datos or {}).items()},
           "android": {"priority": "high", "notification": {"tag": etiqueta[:60]} if etiqueta else {}}}
    if len(temas) == 1:
        msg["topic"] = temas[0]
    else:
        msg["condition"] = " || ".join(f"'{t}' in topics" for t in temas)
    try:
        r = requests.post(f"https://fcm.googleapis.com/v1/projects/{_TOKEN['proyecto']}/messages:send",
                          headers={"Authorization": f"Bearer {tk}"}, json={"message": msg}, timeout=20)
        if r.status_code != 200:
            print(f"  aviso notificaciones: {r.status_code} {r.text[:200]}")
        return r.status_code == 200
    except requests.RequestException as e:
        print(f"  aviso notificaciones: {e}")
        return False
