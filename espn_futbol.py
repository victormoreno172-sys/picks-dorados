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
            eq = {t["homeAway"]: t for t in c["competitors"]}
            dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(TZ)
        except (KeyError, IndexError, ValueError):
            continue
        if "home" not in eq or "away" not in eq:
            continue
        estado = (c.get("status") or e.get("status") or {}).get("type", {})
        hecho = bool(estado.get("completed"))
        p = {"fecha": dt.date(), "hora": dt.strftime("%H:%M"),
             "local": eq["home"]["team"]["displayName"], "visitante": eq["away"]["team"]["displayName"],
             "gl": int(eq["home"]["score"]) if hecho else None,
             "gv": int(eq["away"]["score"]) if hecho else None, "cuotas": {}}
        if estado.get("name") in ("STATUS_POSTPONED", "STATUS_CANCELED"):
            continue
        odds = (c.get("odds") or [{}])[0]
        for clave, mercado in (("homeTeamOdds", "Gana local (1)"), ("awayTeamOdds", "Gana visitante (2)"),
                               ("drawOdds", "Empate (X)")):
            dec = _americana_a_decimal((odds.get(clave) or {}).get("moneyLine"))
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
