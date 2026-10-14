"""
Descarga de datos.

Fuente principal (gratis, sin registro): football-data.co.uk
  - Resultados históricos por liga y temporada, con cuotas medias del mercado.
  - fixtures.csv: próximos partidos de todas las ligas, con cuotas.
Fuente opcional: api.football-data.org (clave gratuita) por si fixtures.csv
todavía no tiene los partidos de hoy.
"""
from __future__ import annotations

import csv
import difflib
import io
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime

import requests

import config
from modelo import Partido

URL_RESULTADOS = "https://www.football-data.co.uk/mmz4281/{temp}/{liga}.csv"
URL_PROXIMOS = "https://www.football-data.co.uk/fixtures.csv"
URL_FDORG = "https://api.football-data.org/v4/matches"


@dataclass
class PartidoProximo:
    liga: str
    fecha: date
    hora: str
    local: str
    visitante: str
    cuotas: dict[str, float] = field(default_factory=dict)  # mercado -> cuota decimal


# ----------------------------------------------------------------- utilidades
def _fecha(txt: str) -> date:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(txt.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Fecha no reconocida: {txt}")


def _num(txt) -> float | None:
    try:
        v = float(txt)
        return v if v > 1 else None
    except (TypeError, ValueError):
        return None


def codigo_temporada(d: date) -> str:
    """Temporada que empieza en julio. 14/10/2026 -> '2627'."""
    inicio = d.year if d.month >= 7 else d.year - 1
    return f"{inicio % 100:02d}{(inicio + 1) % 100:02d}"


def _descargar(url: str, cache: str, max_horas: float) -> str:
    os.makedirs(config.CARPETA_CACHE, exist_ok=True)
    ruta = os.path.join(config.CARPETA_CACHE, cache)
    if os.path.exists(ruta) and time.time() - os.path.getmtime(ruta) < max_horas * 3600:
        with open(ruta, encoding="utf-8") as f:
            return f.read()
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    texto = r.content.decode("utf-8-sig", errors="replace")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return texto


def _filas(texto: str):
    return [f for f in csv.DictReader(io.StringIO(texto)) if f.get("HomeTeam")]


def _cuotas(fila: dict) -> dict[str, float]:
    mapa = {
        "Gana local (1)": "AvgH", "Empate (X)": "AvgD", "Gana visitante (2)": "AvgA",
        "Más de 2.5 goles": "Avg>2.5", "Menos de 2.5 goles": "Avg<2.5",
    }
    out = {}
    for mercado, col in mapa.items():
        v = _num(fila.get(col)) or _num(fila.get(col.replace("Avg", "B365")))
        if v:
            out[mercado] = v
    return out


# --------------------------------------------------------------- históricos
def resultados_desde_csv(texto: str) -> list[Partido]:
    out = []
    for f in _filas(texto):
        hg, ag = f.get("FTHG") or f.get("HG"), f.get("FTAG") or f.get("AG")
        if hg in (None, "") or ag in (None, ""):
            continue
        out.append(Partido(_fecha(f["Date"]), f["HomeTeam"].strip(), f["AwayTeam"].strip(),
                           int(float(hg)), int(float(ag))))
    return out


def historico(liga: str, hoy: date) -> list[Partido]:
    partidos = []
    inicio = int(codigo_temporada(hoy)[:2])
    for k in range(config.TEMPORADAS_HISTORICO):
        a = (inicio - k) % 100
        temp = f"{a:02d}{(a + 1) % 100:02d}"
        horas = 6 if k == 0 else 24 * 30  # la temporada actual se refresca a menudo
        try:
            texto = _descargar(URL_RESULTADOS.format(temp=temp, liga=liga), f"{liga}_{temp}.csv", horas)
            partidos += resultados_desde_csv(texto)
        except requests.RequestException as e:
            print(f"  aviso: no se pudo bajar {liga} {temp}: {e}")
    return partidos


# ------------------------------------------------------------ partidos de hoy
def proximos_desde_csv(texto: str, dia: date) -> list[PartidoProximo]:
    out = []
    for f in _filas(texto):
        liga = f.get("Div", "").strip()
        if liga not in config.LIGAS or _fecha(f["Date"]) != dia:
            continue
        out.append(PartidoProximo(liga, dia, f.get("Time", "").strip(),
                                  f["HomeTeam"].strip(), f["AwayTeam"].strip(), _cuotas(f)))
    return out


def _desde_football_data_org(dia: date, equipos_por_liga: dict[str, list[str]]) -> list[PartidoProximo]:
    """Respaldo: pide los partidos a football-data.org y traduce los nombres de equipo."""
    if not config.FOOTBALL_DATA_ORG_KEY:
        return []
    inv = {cod: liga for liga, (_, cod) in config.LIGAS.items() if cod}
    r = requests.get(URL_FDORG, headers={"X-Auth-Token": config.FOOTBALL_DATA_ORG_KEY},
                     params={"dateFrom": dia.isoformat(), "dateTo": dia.isoformat()}, timeout=30)
    r.raise_for_status()
    out = []
    for m in r.json().get("matches", []):
        liga = inv.get(m["competition"]["code"])
        if not liga:
            continue
        nombres = equipos_por_liga.get(liga, [])
        loc = emparejar_nombre(m["homeTeam"].get("shortName") or m["homeTeam"]["name"], nombres)
        vis = emparejar_nombre(m["awayTeam"].get("shortName") or m["awayTeam"]["name"], nombres)
        if loc and vis:
            utc = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
            from zoneinfo import ZoneInfo
            hora = utc.astimezone(ZoneInfo(config.ZONA_HORARIA)).strftime("%H:%M")
            out.append(PartidoProximo(liga, dia, hora, loc, vis))
    return out


def emparejar_nombre(nombre: str, candidatos: list[str]) -> str | None:
    limpio = (nombre.replace("FC", "").replace("CF", "").replace("Club", "")
              .replace("de Fútbol", "").strip())
    m = difflib.get_close_matches(limpio, candidatos, n=1, cutoff=0.6)
    return m[0] if m else None


def partidos_del_dia(dia: date, equipos_por_liga: dict[str, list[str]]) -> list[PartidoProximo]:
    try:
        lista = proximos_desde_csv(_descargar(URL_PROXIMOS, "fixtures.csv", 3), dia)
    except requests.RequestException as e:
        print(f"  aviso: no se pudo bajar fixtures.csv: {e}")
        lista = []
    if not lista:
        try:
            lista = _desde_football_data_org(dia, equipos_por_liga)
        except requests.RequestException as e:
            print(f"  aviso: football-data.org falló: {e}")
    return sorted(lista, key=lambda p: (p.hora or "99", p.liga))
