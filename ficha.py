"""
Ficha de cada partido (pantalla de detalle de la app): escudos, estadio, alineaciones,
clasificación y últimos partidos de cada equipo. Todo sale de ESPN (gratis, sin clave).

Se empareja cada partido de la app con el de ESPN por liga, fecha, hora y nombres.
"""
from __future__ import annotations

import difflib
import json
import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config

TZ = ZoneInfo(config.ZONA_HORARIA)
CACHE = os.path.join(config.CARPETA_CACHE, "fichas")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://site.api.espn.com/apis/site/v2/sports/{deporte}/{slug}/{que}"

# Nombre de la liga en la app -> (deporte, liga en ESPN)
SLUGS = {
    "LaLiga": ("soccer", "esp.1"), "Segunda División": ("soccer", "esp.2"), "Premier League": ("soccer", "eng.1"),
    "Championship": ("soccer", "eng.2"), "Serie A": ("soccer", "ita.1"), "Bundesliga": ("soccer", "ger.1"),
    "Ligue 1": ("soccer", "fra.1"), "Eredivisie": ("soccer", "ned.1"), "Liga Portugal": ("soccer", "por.1"),
    "MLS": ("soccer", "usa.1"), "Liga Argentina": ("soccer", "arg.1"),
    "Champions League": ("soccer", "uefa.champions"), "Europa League": ("soccer", "uefa.europa"),
    "Conference League": ("soccer", "uefa.europa.conf"),
    "NBA": ("basketball", "nba"), "NBA · Pretemporada": ("basketball", "nba"),
}
DIAS_CON_DETALLE = 3  # alineaciones, clasificación y forma solo para los próximos días


def _get(deporte: str, slug: str, que: str, params: dict, horas: float) -> dict:
    os.makedirs(CACHE, exist_ok=True)
    nombre = f"{deporte}_{slug}_{que}_" + "_".join(f"{k}{v}" for k, v in sorted(params.items())) + ".json"
    ruta = os.path.join(CACHE, nombre.replace("/", "-"))
    if os.path.exists(ruta) and time.time() - os.path.getmtime(ruta) < horas * 3600:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    try:
        r = requests.get(BASE.format(deporte=deporte, slug=slug, que=que), params=params, headers=UA, timeout=30)
        r.raise_for_status()
        datos = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  aviso fichas {slug} {que}: {e}")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
        return {}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return datos


def _norm(t: str) -> str:
    import europa
    return europa.normalizar(t)


def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


def _eventos(deporte: str, slug: str, dia: date) -> list[dict]:
    out = []
    for e in (_get(deporte, slug, "scoreboard", {"dates": f"{dia:%Y%m%d}"}, 3).get("events") or []):
        try:
            c = e["competitions"][0]
            eq = {t["homeAway"]: t for t in c["competitors"]}
            dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(TZ)
            v = c.get("venue") or {}
            out.append({"id": e["id"], "fecha": dt.date(), "hora": dt.strftime("%H:%M"),
                        "local": eq["home"]["team"]["displayName"], "visitante": eq["away"]["team"]["displayName"],
                        "esc": [eq["home"]["team"].get("logo", ""), eq["away"]["team"].get("logo", "")],
                        "estadio": ", ".join(x for x in (v.get("fullName"), (v.get("address") or {}).get("city")) if x)})
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    return out


def _emparejar(p: dict, fecha: date, eventos: list[dict]) -> dict | None:
    mejor, puntos = None, 0.0
    for e in eventos:
        if abs((e["fecha"] - fecha).days) > 1:
            continue
        s = _sim(p["local"], e["local"]) + _sim(p["visitante"], e["visitante"])
        if p.get("hora") and e["hora"] == p["hora"]:
            s += 0.4  # misma hora de inicio: casi seguro que es ese
        if s > puntos:
            mejor, puntos = e, s
    return mejor if puntos >= 1.2 else None


def _alineaciones(s: dict) -> dict | None:
    out = {}
    for r in s.get("rosters") or []:
        jug = r.get("roster") or []
        if not jug:
            continue
        lado = "l" if r.get("homeAway") == "home" else "v"
        tit = [j for j in jug if j.get("starter")]
        sup = [j for j in jug if not j.get("starter")]
        fila = lambda j: [j.get("jersey") or "", (j.get("athlete") or {}).get("displayName") or "?",
                          ((j.get("position") or {}).get("abbreviation") or "")]
        out[lado] = {"form": r.get("formation") or "", "tit": [fila(j) for j in tit], "sup": [fila(j) for j in sup][:12]}
    return out or None


def _forma(s: dict) -> dict | None:
    out = {}
    for i, t in enumerate(s.get("lastFiveGames") or []):
        lado = "l" if i == 0 else "v"
        partidos = []
        for e in (t.get("events") or [])[:5]:
            partidos.append({"r": e.get("gameResult", ""), "m": e.get("score", ""), "a": e.get("atVs", ""),
                             "o": (e.get("opponent") or {}).get("displayName", ""), "f": (e.get("gameDate") or "")[:10]})
        out[lado] = sorted(partidos, key=lambda e: e["f"], reverse=True)  # el más reciente primero
    return out or None


def _tabla(s: dict) -> list | None:
    try:
        grupos = s["standings"]["groups"]
    except (KeyError, TypeError):
        return None
    filas = []
    for g in grupos:
        for e in (g.get("standings") or {}).get("entries") or []:
            st = {x.get("name"): x.get("displayValue") for x in e.get("stats") or []}
            nombre = e.get("team") if isinstance(e.get("team"), str) else (e.get("team") or {}).get("displayName", "")
            filas.append([st.get("rank", ""), nombre, st.get("gamesPlayed", ""), st.get("wins", ""), st.get("ties", ""),
                          st.get("losses", ""), st.get("pointDifferential", ""), st.get("points", "")])
        if len(grupos) > 1:
            filas.append(None)  # separador entre grupos
    return [f for f in filas if f is not None] if filas else None


def enriquecer(datos_app: dict):
    """Añade a cada partido de la app su ficha (campo "fi") y las clasificaciones (datos_app["tablas"])."""
    hoy = datetime.now(TZ).date()
    tablas, n_fichas, n_detalle = {}, 0, 0
    cache_ev: dict[tuple, list] = {}
    for dia in datos_app.get("dias", []):
        fecha = date.fromisoformat(dia["fecha"])
        for p in dia["partidos"]:
            ds = SLUGS.get(p.get("liga"))
            if not ds:
                continue
            evs = []
            for d in (fecha - timedelta(days=1), fecha, fecha + timedelta(days=1)):
                clave = (*ds, d)
                if clave not in cache_ev:
                    cache_ev[clave] = _eventos(*ds, d)
                evs += cache_ev[clave]
            e = _emparejar(p, fecha, evs)
            if not e:
                continue
            fi = {"id": e["id"], "slug": ds[1], "esc": e["esc"], "estadio": e["estadio"], "n": [e["local"], e["visitante"]]}
            if (fecha - hoy).days < DIAS_CON_DETALLE:
                horas = 0.5 if fecha == hoy else 3
                s = _get(*ds, "summary", {"event": e["id"]}, horas)
                if s:
                    al, fo, tb = _alineaciones(s), _forma(s), _tabla(s)
                    if al:
                        fi["alin"] = al
                    if fo:
                        fi["forma"] = fo
                    if tb and ds[1] not in tablas:
                        tablas[ds[1]] = tb
                    n_detalle += 1
            p["fi"] = fi
            n_fichas += 1
    datos_app["tablas"] = tablas
    print(f"  fichas: {n_fichas} partidos con escudos y estadio, {n_detalle} con detalle, {len(tablas)} clasificaciones")
