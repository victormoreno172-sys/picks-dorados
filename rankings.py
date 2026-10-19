"""
Rankings oficiales (o los de referencia) para poner la posición de cada equipo o jugador:
  CS2 -> ranking mundial oficial de Valve (VRS)   Valorant -> vlr.gg   LoL -> Global Power Rankings de Riot
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
    """Ranking mundial oficial de Valve (VRS), el que decide las invitaciones a los Majors."""
    base = "https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/live"
    try:
        anos = sorted(x["name"] for x in json.loads(_get(base) or "[]") if x.get("type") == "dir")
        if not anos:
            return {}
        fich = sorted(x["name"] for x in json.loads(_get(f"{base}/{anos[-1]}") or "[]") if "global" in x.get("name", ""))
    except (ValueError, TypeError, KeyError):
        return {}
    if not fich:
        return {}
    t = _get(f"https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/main/live/{anos[-1]}/{fich[-1]}")
    out = {}
    for m in re.finditer(r"^\|\s*(\d+)\s*\|\s*\d+\s*\|\s*([^|]+?)\s*\|", t, re.M):
        out.setdefault(m.group(2), int(m.group(1)))
    return out


REGION_VLR = {"Europe": "Europa", "North America": "Norteamérica", "Brazil": "Brasil", "Asia-Pacific": "Asia-Pacífico",
              "Korea": "Corea", "China": "China", "Japan": "Japón", "LA-S": "Latam Sur", "LA-N": "Latam Norte",
              "Oceania": "Oceanía", "MENA": "MENA", "GC": "Game Changers", "Collegiate": "universitario"}


def valorant() -> dict:
    """Ranking de vlr.gg: va por regiones ("#1 Europa")."""
    t = _get("https://www.vlr.gg/rankings")
    out = {}
    for bloque in t.split('class="wf-label mod-large mod-world">')[1:]:
        region = html.unescape(bloque.split("<", 1)[0]).strip()
        for m in re.finditer(r'class="rank-item-rank"[^>]*>\s*<a[^>]*>\s*(\d+)\s*</a>.*?class="rank-item-team"[^>]*>.*?alt="([^"]+)"', bloque, re.S):
            out.setdefault(html.unescape(m.group(2)).strip(), (int(m.group(1)), REGION_VLR.get(region, region)))
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
    for clave, f, etiqueta in (("e-cs2", cs2, "mundial"), ("e-val", valorant, "VLR"), ("e-lol", lol, "mundial"),
                               ("t-atp", lambda: tenis("atp"), "ATP"), ("t-wta", lambda: tenis("wta"), "WTA")):
        try:
            d = f()
        except Exception:  # noqa: BLE001
            d = {}
        if d:
            out[clave] = {n: (f"#{p[0]} {p[1]}" if isinstance(p, tuple) else f"#{p} {etiqueta}") for n, p in d.items()}
        print(f"  ranking {etiqueta}: {len(d)}")
    return out
