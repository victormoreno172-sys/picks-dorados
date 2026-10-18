"""
Escudos que le faltan a ESPN (equipos de categorías bajas que juegan las copas): se buscan
en TheSportsDB por nombre y se guardan para siempre en caché (los que no aparecen se reintentan
al mes). Como la clave gratuita va lenta, cada actualización busca como mucho unos cuantos.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

import config

RUTA = os.path.join(config.CARPETA_CACHE, "escudos.json")
URL = "https://www.thesportsdb.com/api/v1/json/{clave}/searchteams.php"
PREFIJOS = r"^(cd|ud|sd|cf|ad|ac|fc|sc|sv|vv|rkvv|cs|ca|ce|ec|se|sad|rcd|rc|club|atletico|atlético|1\.|ss|us|asd)\s+"
MAX_POR_VEZ = 70
_cache: dict | None = None
_buscados = 0


def _cargar() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(RUTA, encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def guardar():
    if _cache is not None:
        os.makedirs(os.path.dirname(RUTA), exist_ok=True)
        with open(RUTA, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)


def _buscar(nombre: str, pais: str) -> str:
    global _buscados
    clave = config.THESPORTSDB_KEY or "123"
    variantes = [nombre]
    corto = re.sub(PREFIJOS, "", nombre, flags=re.I).strip()
    corto = re.sub(r"\s+(cf|fc|sc|sv|cd|ud|ac|1\d{3}|'\d\d)$", "", corto, flags=re.I).strip()
    if corto and corto.lower() != nombre.lower():
        variantes.append(corto)
    for v in variantes:
        if _buscados >= MAX_POR_VEZ:
            return None
        _buscados += 1
        try:
            r = requests.get(URL.format(clave=clave), params={"t": v}, timeout=20)
            if r.status_code == 429:
                time.sleep(20)
                continue
            equipos = (r.json() or {}).get("teams") or []
        except (requests.RequestException, ValueError):
            equipos = []
        time.sleep(2.1)  # la clave gratuita permite ~30 peticiones por minuto
        futbol = [e for e in equipos if (e.get("strSport") or "") == "Soccer" and e.get("strBadge")]
        del_pais = [e for e in futbol if pais and pais.lower() in (e.get("strCountry") or "").lower()]
        elegido = (del_pais or (futbol if not pais else []))[:1]
        if elegido:
            return elegido[0]["strBadge"] + "/small"
    return ""


def escudo(nombre: str, pais: str = "") -> str:
    """URL del escudo o "" si no se encuentra (o no toca buscar todavía)."""
    if not nombre or re.match(r"^(tbd|por decidir)", nombre, re.I):
        return ""
    c = _cargar()
    k = f"{pais}|{nombre}"
    v = c.get(k)
    if v and v.get("u"):
        return v["u"]
    if v and time.time() - v.get("t", 0) < 30 * 86400:
        return ""
    u = _buscar(nombre, pais)
    if u is None:  # cupo de esta vez agotado: otra vez será
        return ""
    c[k] = {"u": u, "t": time.time()}
    return u
