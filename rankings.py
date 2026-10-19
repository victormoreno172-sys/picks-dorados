"""
Rankings oficiales (o los de referencia) para poner la posición de cada equipo o jugador:
  CS2 -> ranking mundial de HLTV (dust2.us)   Valorant -> vlr.gg   LoL -> Global Power Rankings de Riot
  Tenis -> ranking ATP / WTA (ESPN)
Devuelven {nombre: posición}.
"""
from __future__ import annotations

import html
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept": "text/html,application/json"}
_C: dict = {}


def _get(url: str) -> str:
    if url not in _C:
        try:
            r = requests.get(url, headers=UA, timeout=30)
            _C[url] = r.text if r.ok else ""
        except requests.RequestException:
            _C[url] = ""
    return _C[url]


def cs2() -> dict:
    t = _get("https://www.dust2.us/ranking")
    out = {}
    for bloque in t.split('class="ranked-team')[1:]:
        pos = re.search(r'class="position"[^>]*>\s*#?(\d+)', bloque)
        nombre = re.search(r'class="name"[^>]*>([^<]+)<', bloque)
        if pos and nombre:
            out.setdefault(html.unescape(nombre.group(1)).strip(), int(pos.group(1)))
    return out


def valorant() -> dict:
    t = _get("https://www.vlr.gg/rankings")
    out = {}
    for m in re.finditer(r'class="rank-item-rank"[^>]*>\s*<a[^>]*>\s*(\d+)\s*</a>.*?class="rank-item-team"[^>]*>.*?<div>\s*([^<\n\t]+)', t, re.S):
        out.setdefault(html.unescape(m.group(2)).strip(), int(m.group(1)))
    return out


def lol() -> dict:
    t = _get("https://lolesports.com/en-US/gpr")
    out = {}
    for m in re.finditer(r'"name":"([^"]+)","slug":"[^"]+"\},"teamGPRHistory":\[\{[^\]]*?"rank":(\d+)', t):
        out.setdefault(m.group(1), int(m.group(2)))
    return out


def tenis(tour: str) -> dict:
    try:
        j = json.loads(_get(f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/rankings") or "{}")
    except ValueError:
        return {}
    out = {}
    for rk in j.get("rankings") or []:
        for r in rk.get("ranks") or []:
            n = (r.get("athlete") or {}).get("displayName")
            if n and r.get("current"):
                out.setdefault(n, int(r["current"]))
    return out


def todos() -> dict:
    out = {}
    for clave, f, etiqueta in (("e-cs2", cs2, "HLTV"), ("e-val", valorant, "VLR"), ("e-lol", lol, "Riot"),
                               ("t-atp", lambda: tenis("atp"), "ATP"), ("t-wta", lambda: tenis("wta"), "WTA")):
        try:
            d = f()
        except Exception:  # noqa: BLE001
            d = {}
        if d:
            out[clave] = {n: f"#{p} {etiqueta}" for n, p in d.items()}
        print(f"  ranking {etiqueta}: {len(d)}")
    return out
