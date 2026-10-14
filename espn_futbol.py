"""
Ligas de fútbol que football-data.co.uk no tiene en el formato normal: se leen
de ESPN (calendario, resultados y, a veces, cuotas). Ahora mismo: MLS.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config
from datos import PartidoProximo
from modelo import Partido

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
CACHE = os.path.join(config.CARPETA_CACHE, "espn_futbol")
TZ = ZoneInfo(config.ZONA_HORARIA)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def _get(slug: str, dia: date, horas: float | None):
    """Partidos de un día (con caché; horas=None -> no caduca)."""
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, f"{slug}_{dia:%Y%m%d}.json")
    if os.path.exists(ruta) and (horas is None or time.time() - os.path.getmtime(ruta) < horas * 3600):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    try:
        r = requests.get(URL.format(slug=slug), headers=UA, timeout=40,
                         params={"dates": f"{dia:%Y%m%d}"})
        r.raise_for_status()
        datos = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  aviso ESPN {slug}: {e}")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
        return {}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return datos


def _americana_a_decimal(ml) -> float | None:
    try:
        ml = float(ml)
    except (TypeError, ValueError):
        return None
    if ml == 0:
        return None
    return round(1 + (ml / 100 if ml > 0 else 100 / -ml), 2)


def parsear(datos: dict) -> list[dict]:
    """Lista de partidos: fecha/hora de Madrid, equipos, goles (si terminó) y cuotas."""
    out = []
    for e in (datos or {}).get("events", []):
        try:
            c = e["competitions"][0]
            eq = {t["homeAway"]: t for t in c["competitors"] if t and t.get("team")}
            dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(TZ)
        except (KeyError, IndexError, ValueError, TypeError, AttributeError):
            continue
        if "home" not in eq or "away" not in eq:
            continue
        estado = (c.get("status") or e.get("status") or {}).get("type") or {}
        hecho = bool(estado.get("completed"))
        p = {"fecha": dt.date(), "hora": dt.strftime("%H:%M"),
             "local": eq["home"]["team"]["displayName"], "visitante": eq["away"]["team"]["displayName"],
             "gl": int(eq["home"]["score"]) if hecho else None,
             "gv": int(eq["away"]["score"]) if hecho else None, "cuotas": {}}
        if estado.get("name") in ("STATUS_POSTPONED", "STATUS_CANCELED"):
            continue
        odds = (c.get("odds") or [{}])[0] or {}
        for clave, mercado in (("homeTeamOdds", "Gana local (1)"), ("awayTeamOdds", "Gana visitante (2)"),
                               ("drawOdds", "Empate (X)")):
            dec = _americana_a_decimal((odds.get(clave) or {}).get("moneyLine")) if isinstance(odds.get(clave), dict) else None
            if dec:
                p["cuotas"][mercado] = dec
        out.append(p)
    return out


def historico(liga: str, hoy: date) -> list[Partido]:
    slug = config.LIGAS_ESPN[liga][1]
    out = []
    d = date(hoy.year - 1, 2, 1)  # la MLS va por años naturales (febrero-diciembre)
    while d < hoy:
        if d.month in (1,):  # en enero no hay MLS
            d = date(d.year, 2, 1)
            continue
        pasado = d < hoy - timedelta(days=3)  # un día ya cerrado no cambia
        for p in parsear(_get(slug, d, None if pasado else 6)):
            if p["gl"] is not None:
                out.append(Partido(p["fecha"], p["local"], p["visitante"], p["gl"], p["gv"]))
        d += timedelta(days=1)
    # mismo partido visto en dos días (zona horaria): quitar duplicados
    unicos = {(p.fecha, p.local, p.visitante): p for p in out}
    return list(unicos.values())


def proximos(liga: str, hoy: date, n_dias: int) -> dict[date, list[PartidoProximo]]:
    slug = config.LIGAS_ESPN[liga][1]
    salida: dict[date, list[PartidoProximo]] = {}
    vistos = set()
    for k in range(-1, n_dias + 1):
        for p in parsear(_get(slug, hoy + timedelta(days=k), 3)):
            clave = (p["fecha"], p["local"], p["visitante"])
            if p["gl"] is None and hoy <= p["fecha"] < hoy + timedelta(days=n_dias) and clave not in vistos:
                vistos.add(clave)
                salida.setdefault(p["fecha"], []).append(
                    PartidoProximo(liga, p["fecha"], p["hora"], p["local"], p["visitante"], p["cuotas"]))
    return salida


# --------------------------------------------------------------------------
# Respaldo del calendario de las ligas europeas: football-data.co.uk solo pone
# en fixtures.csv la jornada inminente (a veces solo la del jueves/viernes), así
# que el calendario de ESPN completa lo que falte. Los nombres de ESPN se traducen
# a los de football-data aprendiendo de partidos ya jugados (misma fecha y mismo
# resultado en las dos fuentes), y si no, con el traductor de las copas europeas.
SLUGS = {"SP1": "esp.1", "SP2": "esp.2", "E0": "eng.1", "E1": "eng.2", "I1": "ita.1",
         "D1": "ger.1", "F1": "fra.1", "N1": "ned.1", "P1": "por.1"}


def _aprender_nombres(slug: str, hist: list[Partido], hoy: date) -> dict[str, str]:
    """ESPN -> football-data, con los partidos de los últimos 40 días."""
    por_dia: dict[date, list[Partido]] = {}
    for p in hist:
        if hoy - timedelta(days=40) <= p.fecha < hoy - timedelta(days=1):
            por_dia.setdefault(p.fecha, []).append(p)
    votos: dict[str, dict[str, int]] = {}
    for d in sorted(por_dia):
        for e in parsear(_get(slug, d, None)):
            if e["gl"] is None:
                continue
            cand = [p for k in (-1, 0, 1) for p in por_dia.get(e["fecha"] + timedelta(days=k), [])
                    if (p.goles_local, p.goles_visitante) == (e["gl"], e["gv"])]
            if len(cand) == 1:
                for a, b in ((e["local"], cand[0].local), (e["visitante"], cand[0].visitante)):
                    votos.setdefault(a, {}).setdefault(b, 0)
                    votos[a][b] += 1
    return {a: max(v, key=v.get) for a, v in votos.items()}


def proximos_ligas(hoy: date, n_dias: int, historicos: dict[str, list[Partido]]) -> dict[date, list[PartidoProximo]]:
    import europa
    salida: dict[date, list[PartidoProximo]] = {}
    for liga, slug in SLUGS.items():
        hist = historicos.get(liga) or []
        if not hist:
            continue
        equipos = {p.local for p in hist if p.fecha > hoy - timedelta(days=400)} | \
                  {p.visitante for p in hist if p.fecha > hoy - timedelta(days=400)}
        try:
            aprendidos = _aprender_nombres(slug, hist, hoy)
        except Exception as e:
            print(f"  aviso ESPN {liga}: {e}")
            aprendidos = {}
        emp = europa.Emparejador({"X": equipos})
        vistos, sin = set(), set()
        for k in range(-1, n_dias + 1):
            for e in parsear(_get(slug, hoy + timedelta(days=k), 3)):
                if e["gl"] is not None or not (hoy <= e["fecha"] < hoy + timedelta(days=n_dias)):
                    continue
                nombres = []
                for n in (e["local"], e["visitante"]):
                    t = aprendidos.get(n)
                    if t not in equipos:
                        t = emp(n, "X")
                    nombres.append(t if t in equipos else None)
                if None in nombres:
                    sin.add(f"{e['local']} - {e['visitante']}")
                    continue
                clave = (e["fecha"], *nombres)
                if clave in vistos:
                    continue
                vistos.add(clave)
                salida.setdefault(e["fecha"], []).append(
                    PartidoProximo(liga, e["fecha"], e["hora"], nombres[0], nombres[1], e["cuotas"]))
        print(f"  calendario ESPN {liga}: {len(vistos)} partidos ({len(aprendidos)} nombres aprendidos)"
              + (f", sin traducir: {sorted(sin)[:4]}" if sin else ""))
    return salida
