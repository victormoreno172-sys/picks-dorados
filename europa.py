"""
Champions League, Europa League y Conference League.

El problema de las copas europeas es comparar equipos de ligas distintas
(¿cuánto vale el 3º de Países Bajos contra el 8º de Italia?). Para eso se
entrena UN modelo conjunto con:
  - las ligas nacionales de media Europa (football-data.co.uk), y
  - los partidos europeos de las últimas temporadas (openfootball + TheSportsDB),
que son los que "conectan" las ligas entre sí.

Calendario de partidos europeos: TheSportsDB (clave pública gratuita "123").
"""
from __future__ import annotations

import csv
import io
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import requests
from scipy.optimize import minimize
from scipy.stats import poisson

import config
import datos
from modelo import MAX_GOLES

URL_TSDB = "https://www.thesportsdb.com/api/v1/json/{clave}/"
URL_OPENFOOTBALL = "https://raw.githubusercontent.com/openfootball/champions-league/master/{temp}/{comp}.txt"
URL_NUEVAS = "https://www.football-data.co.uk/new/{codigo}.csv"

# Código de país (el que usa openfootball) -> ligas de football-data.co.uk
LIGAS_PAIS = {
    "ENG": ["E0", "E1"], "ESP": ["SP1", "SP2"], "ITA": ["I1", "I2"], "GER": ["D1", "D2"],
    "FRA": ["F1", "F2"], "NED": ["N1"], "POR": ["P1"], "BEL": ["B1"], "TUR": ["T1"],
    "GRE": ["G1"], "SCO": ["SC0"],
    # Ligas del formato "nuevo" (un archivo con todas las temporadas)
    "AUT": ["AUT"], "SUI": ["SWZ"], "DEN": ["DNK"], "NOR": ["NOR"], "SWE": ["SWE"],
    "POL": ["POL"], "ROU": ["ROU"], "IRL": ["IRL"], "FIN": ["FIN"],
}
FORMATO_NUEVO = {"AUT", "SWZ", "DNK", "NOR", "SWE", "POL", "ROU", "IRL", "FIN"}

# Nombres que football-data.co.uk abrevia a su manera (clave ya normalizada)
ALIAS = {
    "manchester city": "Man City", "manchester united": "Man United", "man utd": "Man United",
    "tottenham hotspur": "Tottenham", "newcastle united": "Newcastle", "west ham united": "West Ham",
    "nottingham forest": "Nott'm Forest", "brighton and hove albion": "Brighton",
    "brighton hove albion": "Brighton", "wolverhampton wanderers": "Wolves",
    "atletico madrid": "Ath Madrid", "atletico de madrid": "Ath Madrid", "athletic": "Ath Bilbao",
    "athletic bilbao": "Ath Bilbao", "real betis": "Betis", "celta vigo": "Celta", "celta": "Celta",
    "real sociedad": "Sociedad", "rayo vallecano": "Vallecano",
    "paris saint germain": "Paris SG", "psg": "Paris SG", "olympique lyonnais": "Lyon",
    "olympique marseille": "Marseille", "olympique de marseille": "Marseille", "losc lille": "Lille",
    "stade rennais": "Rennes", "stade brestois 29": "Brest", "stade brestois": "Brest",
    "bayern munich": "Bayern Munich", "bayern munchen": "Bayern Munich",
    "borussia dortmund": "Dortmund", "bayer leverkusen": "Leverkusen", "bayer 04 leverkusen": "Leverkusen",
    "eintracht frankfurt": "Ein Frankfurt", "borussia monchengladbach": "M'gladbach",
    "vfb stuttgart": "Stuttgart", "tsg hoffenheim": "Hoffenheim", "1899 hoffenheim": "Hoffenheim",
    "sc freiburg": "Freiburg", "1 fsv mainz 05": "Mainz", "mainz 05": "Mainz", "union berlin": "Union Berlin",
    "vfl wolfsburg": "Wolfsburg", "werder bremen": "Werder Bremen",
    "inter": "Inter", "internazionale": "Inter", "inter milan": "Inter", "milan": "Milan", "ac milan": "Milan",
    "as roma": "Roma", "ss lazio": "Lazio", "ssc napoli": "Napoli", "atalanta bc": "Atalanta",
    "acf fiorentina": "Fiorentina", "bologna 1909": "Bologna",
    "sporting": "Sp Lisbon", "sporting cp": "Sp Lisbon", "sporting lisbon": "Sp Lisbon",
    "sporting clube de portugal": "Sp Lisbon", "braga": "Sp Braga", "sporting braga": "Sp Braga",
    "vitoria guimaraes": "Guimaraes", "psv": "PSV Eindhoven", "az": "AZ Alkmaar",
    "union saint gilloise": "St. Gilloise", "royale union saint gilloise": "St. Gilloise",
    "union sg": "St. Gilloise", "club brugge kv": "Club Brugge", "brugge": "Club Brugge",
    "heart of midlothian": "Hearts", "red bull salzburg": "Salzburg", "rb salzburg": "Salzburg",
    "olympiacos": "Olympiakos", "olympiacos piraeus": "Olympiakos", "fc copenhagen": "FC Copenhagen",
    "kobenhavn": "FC Copenhagen", "copenhagen": "FC Copenhagen", "fc midtjylland": "Midtjylland",
    "bodo glimt": "Bodo/Glimt", "fk bodo glimt": "Bodo/Glimt", "molde fk": "Molde",
    "malmo ff": "Malmo FF", "malmo": "Malmo FF", "young boys": "Young Boys", "bsc young boys": "Young Boys",
    "fc basel": "Basel", "basel 1893": "Basel", "legia warsaw": "Legia", "legia warszawa": "Legia",
    "lech poznan": "Lech", "fcsb": "FCSB", "steaua bucuresti": "FCSB",
}

QUITAR = {"fc", "cf", "afc", "ac", "sc", "sk", "fk", "bk", "if", "ik", "sv", "club", "de", "the", "cd",
          "ud", "rc", "rcd", "cp", "sad", "kv", "krc", "rsc", "nk", "gnk", "hnk", "pfc", "ofk", "aif",
          "ff", "calcio", "1907", "1909", "1913", "1846", "04", "05", "07", "09", "osc", "royal"}
ESPECIALES = str.maketrans({"ø": "o", "æ": "ae", "ß": "ss", "ł": "l", "đ": "d", "ı": "i", "œ": "oe"})


def normalizar(nombre: str) -> str:
    t = nombre.lower().translate(ESPECIALES)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"\([a-z]{3}\)", " ", t)          # quita "(ESP)" de openfootball
    t = t.replace("&", " and ")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    palabras = [p for p in t.split() if p not in QUITAR]
    return " ".join(palabras) or t.strip()


class Emparejador:
    """Traduce nombres de equipo de cualquier fuente al nombre de football-data.co.uk."""

    def __init__(self, equipos_por_pais: dict[str, set[str]]):
        self.por_pais = {p: {normalizar(e): e for e in es} for p, es in equipos_por_pais.items()}
        self.todos = {}
        for d in self.por_pais.values():
            self.todos.update(d)
        self.cache: dict[tuple[str, str | None], str] = {}

    def __call__(self, nombre: str, pais: str | None = None) -> str:
        clave = (nombre, pais)
        if clave not in self.cache:
            self.cache[clave] = self._buscar(nombre, pais)
        return self.cache[clave]

    def _buscar(self, nombre: str, pais: str | None) -> str:
        import difflib
        n = normalizar(nombre)
        if n in ALIAS:
            return ALIAS[n]
        candidatos = self.por_pais.get(pais, {}) if pais else self.todos
        if n in candidatos:
            return candidatos[n]
        # el nombre corto está contenido en el largo ("Dinamo Zagreb" ~ "Gnk Dinamo Zagreb")
        # (solo dentro de un país: a nivel global "Inter Turku" contendría a "Inter")
        if pais:
            tokens = set(n.split())
            contenidos = [c for c in candidatos if c and (set(c.split()) <= tokens or tokens <= set(c.split()))]
            if len(contenidos) == 1:
                return candidatos[contenidos[0]]
        corte = 0.75 if pais else 0.86
        m = difflib.get_close_matches(n, list(candidatos), n=1, cutoff=corte)
        if m:
            return candidatos[m[0]]
        return "~" + n  # equipo sin liga en nuestros datos: se identifica por su nombre normalizado


# ------------------------------------------------------------------ datos
@dataclass
class PartidoEu:
    fecha: date
    local: str
    visitante: str
    gl: int
    gv: int
    europeo: bool


def _historico_nuevo(codigo: str, desde: date) -> list[PartidoEu]:
    texto = datos._descargar(URL_NUEVAS.format(codigo=codigo), f"nuevo_{codigo}.csv", 12)
    out = []
    for f in csv.DictReader(io.StringIO(texto)):
        try:
            d = datos._fecha(f["Date"])
            if d >= desde and f.get("HG") not in (None, ""):
                out.append(PartidoEu(d, f["Home"].strip(), f["Away"].strip(), int(float(f["HG"])),
                                     int(float(f["AG"])), False))
        except (ValueError, KeyError):
            continue
    return out


def domesticos(hoy: date) -> tuple[list[PartidoEu], dict[str, set[str]]]:
    desde = hoy - timedelta(days=365 * config.TEMPORADAS_HISTORICO)
    partidos, equipos = [], {}
    for pais, codigos in LIGAS_PAIS.items():
        equipos[pais] = set()
        for cod in codigos:
            try:
                if cod in FORMATO_NUEVO:
                    lista = _historico_nuevo(cod, desde)
                else:
                    lista = [PartidoEu(p.fecha, p.local, p.visitante, p.goles_local, p.goles_visitante, False)
                             for p in datos.historico(cod, hoy)]
            except requests.RequestException as e:
                print(f"  aviso europa: {cod} no disponible ({e})")
                continue
            partidos += lista
            for p in lista:
                equipos[pais] |= {p.local, p.visitante}
    return partidos, equipos


RE_FECHA = re.compile(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+([A-Z][a-z]{2})\w*\s+(\d{1,2})\s+(\d{4})")
RE_FECHA_CORTA = re.compile(r"\[?(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+([A-Z][a-z]{2})\w*/?(\d{1,2})\]?")
RE_PARTIDO = re.compile(r"^\s*(?:\d{1,2}[:.]\d{2}\s+)?(.+?\([A-Z]{3}\))\s+v\s+(.+?\([A-Z]{3}\))\s+(\d+)-(\d+)")
MESES = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
                                     "Oct", "Nov", "Dec"], 1)}


def parsear_openfootball(texto: str, anio_inicio: int) -> list[tuple[date, str, str, str, str, int, int]]:
    """Devuelve (fecha, local, país_local, visitante, país_visitante, gl, gv)."""
    out, fecha = [], None
    for linea in texto.splitlines():
        m = RE_FECHA.search(linea)
        if m:
            fecha = date(int(m.group(3)), MESES[m.group(1)], int(m.group(2)))
        else:
            m = RE_FECHA_CORTA.search(linea)
            if m and m.group(1) in MESES and not RE_PARTIDO.match(linea):
                mes = MESES[m.group(1)]
                fecha = date(anio_inicio if mes >= 7 else anio_inicio + 1, mes, int(m.group(2)))
        p = RE_PARTIDO.match(linea)
        if p and fecha:
            l, v = p.group(1).strip(), p.group(2).strip()
            out.append((fecha, re.sub(r"\s*\([A-Z]{3}\)$", "", l), l[-4:-1],
                        re.sub(r"\s*\([A-Z]{3}\)$", "", v), v[-4:-1], int(p.group(3)), int(p.group(4))))
    return out


def historico_europeo(hoy: date, emparejar: Emparejador) -> list[PartidoEu]:
    out = []
    inicio_actual = hoy.year if hoy.month >= 7 else hoy.year - 1
    for k in range(1, config.TEMPORADAS_HISTORICO + 1):
        a = inicio_actual - k
        temp = f"{a}-{(a + 1) % 100:02d}"
        for comp in ("cl", "el", "conf"):
            try:
                texto = datos._descargar(URL_OPENFOOTBALL.format(temp=temp, comp=comp),
                                         f"of_{temp}_{comp}.txt", 24 * 7)
            except requests.RequestException:
                continue
            for f, l, pl, v, pv, gl, gv in parsear_openfootball(texto, a):
                out.append(PartidoEu(f, emparejar(l, pl), emparejar(v, pv), gl, gv, True))
    return out


# --------------------------------------------------------------- calendario
@dataclass
class PartidoEuropeo:
    comp: str          # UCL / UEL / UECL
    fecha: date        # día en Madrid
    hora: str
    local: str         # nombre para mostrar
    visitante: str
    gl: int | None = None
    gv: int | None = None


def _tsdb(ruta: str) -> list[dict]:
    url = URL_TSDB.format(clave=config.THESPORTSDB_KEY or "123") + ruta
    for intento in range(3):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 429:
                time.sleep(20)
                continue
            r.raise_for_status()
            return r.json().get("events") or []
        except (requests.RequestException, ValueError) as e:
            if intento == 2:
                print(f"  aviso TheSportsDB {ruta}: {e}")
        time.sleep(3)
    return []


def calendario_europeo(temporada: str) -> list[PartidoEuropeo]:
    """Todos los partidos de la temporada que da la API, con resultado si ya se jugaron."""
    tz = ZoneInfo(config.ZONA_HORARIA)
    vistos, out = set(), []
    hoy = datetime.now(tz).date()
    for comp, (_, lid) in config.EUROPA.items():
        eventos = []
        for r in range(1, 11):
            eventos += _tsdb(f"eventsround.php?id={lid}&r={r}&s={temporada}")
            time.sleep(2.1)  # la clave gratuita permite ~30 peticiones por minuto
        for k in range(0, 8):  # complementa por días (la clave gratuita corta algunas jornadas)
            eventos += _tsdb(f"eventsday.php?d={hoy + timedelta(days=k)}&l={lid}")
            time.sleep(2.1)
        for e in eventos:
            if e.get("idEvent") in vistos:
                continue
            vistos.add(e.get("idEvent"))
            ts = e.get("strTimestamp")
            if ts:
                dt = datetime.fromisoformat(ts.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
                fecha, hora = dt.date(), dt.strftime("%H:%M")
            elif e.get("dateEvent"):
                fecha, hora = date.fromisoformat(e["dateEvent"]), ""
            else:
                continue
            gl, gv = e.get("intHomeScore"), e.get("intAwayScore")
            jugado = gl not in (None, "") and gv not in (None, "") and e.get("strStatus") not in ("NS", "Postponed")
            out.append(PartidoEuropeo(comp, fecha, hora, e["strHomeTeam"], e["strAwayTeam"],
                                      int(gl) if jugado else None, int(gv) if jugado else None))
    return out


# ------------------------------------------------------------------- modelo
class ModeloEuropeo:
    """Poisson conjunto para toda Europa. Misma interfaz que ModeloDixonColes."""

    def __init__(self, xi: float = 0.0019, rho: float = -0.05, min_partidos: int = 6):
        self.xi, self.rho, self.min_partidos = xi, rho, min_partidos
        self.mapa: dict[str, str] = {}  # nombre mostrado -> nombre interno

    def ajustar(self, partidos: list[PartidoEu], hasta: date) -> "ModeloEuropeo":
        partidos = [p for p in partidos if p.fecha < hasta]
        equipos = sorted({p.local for p in partidos} | {p.visitante for p in partidos})
        idx = {e: i for i, e in enumerate(equipos)}
        n = len(equipos)
        h = np.array([idx[p.local] for p in partidos])
        a = np.array([idx[p.visitante] for p in partidos])
        x = np.array([p.gl for p in partidos], dtype=float)
        y = np.array([p.gv for p in partidos], dtype=float)
        eu = np.array([p.europeo for p in partidos], dtype=float)
        w = np.exp(-self.xi * np.array([(hasta - p.fecha).days for p in partidos], dtype=float))
        w = w * np.where(eu > 0, 2.0, 1.0)  # los partidos europeos valen doble: son los que unen ligas
        lam_reg = 2.0  # regularización: equipos con pocos datos se acercan a la media

        def f(theta):
            att, dfn = theta[:n], theta[n:2 * n]
            c0, hd, he = theta[2 * n:]
            ll = att[h] + dfn[a] + c0 + hd * (1 - eu) + he * eu
            lm = att[a] + dfn[h] + c0
            lam, mu = np.exp(ll), np.exp(lm)
            nll = -np.sum(w * (x * ll - lam + y * lm - mu)) + lam_reg * (att @ att + dfn @ dfn)
            r1, r2 = w * (x - lam), w * (y - mu)
            g_att = -(np.bincount(h, r1, n) + np.bincount(a, r2, n)) + 2 * lam_reg * att
            g_dfn = -(np.bincount(a, r1, n) + np.bincount(h, r2, n)) + 2 * lam_reg * dfn
            g = np.concatenate([g_att, g_dfn, [-(r1.sum() + r2.sum()),
                                               -np.sum(r1 * (1 - eu)), -np.sum(r1 * eu)]])
            return nll, g

        res = minimize(f, np.zeros(2 * n + 3), jac=True, method="L-BFGS-B")
        self.equipos = equipos
        self.att = dict(zip(equipos, res.x[:n]))
        self.dfn = dict(zip(equipos, res.x[n:2 * n]))
        self.c0, self.campo_dom, self.campo_eu = res.x[2 * n:]
        self.n_partidos = dict(zip(equipos, np.bincount(h, minlength=n) + np.bincount(a, minlength=n)))
        print(f"  modelo europeo: {n} equipos, {len(partidos)} partidos, "
              f"ventaja local en Europa {np.exp(self.campo_eu):.2f}x")
        return self

    def registrar(self, mostrado: str, interno: str):
        self.mapa[mostrado] = interno

    def conoce(self, equipo: str) -> bool:
        i = self.mapa.get(equipo, equipo)
        return self.n_partidos.get(i, 0) >= self.min_partidos

    def goles_esperados(self, local: str, visitante: str) -> tuple[float, float]:
        l, v = self.mapa.get(local, local), self.mapa.get(visitante, visitante)
        lam = np.exp(self.att[l] + self.dfn[v] + self.c0 + self.campo_eu)
        mu = np.exp(self.att[v] + self.dfn[l] + self.c0)
        return float(lam), float(mu)

    def tabla_marcadores(self, local: str, visitante: str) -> np.ndarray:
        lam, mu = self.goles_esperados(local, visitante)
        g = np.arange(MAX_GOLES + 1)
        m = np.outer(poisson.pmf(g, lam), poisson.pmf(g, mu))
        m[0, 0] *= 1 - lam * mu * self.rho
        m[0, 1] *= 1 + lam * self.rho
        m[1, 0] *= 1 + mu * self.rho
        m[1, 1] *= 1 - self.rho
        return m / m.sum()


# ------------------------------------------------------------- todo junto
def preparar(hoy: date, n_dias: int):
    """Devuelve (partidos europeos de los próximos n_dias, modelo) o ([], None)."""
    inicio = hoy.year if hoy.month >= 7 else hoy.year - 1
    calendario = calendario_europeo(f"{inicio}-{inicio + 1}")
    proximos = [p for p in calendario if hoy <= p.fecha < hoy + timedelta(days=n_dias) and p.gl is None]
    print(f"  europa: {len(calendario)} partidos en el calendario, {len(proximos)} próximos")
    if not proximos:
        return [], None

    dom, equipos = domesticos(hoy)
    emparejar = Emparejador(equipos)
    hist = historico_europeo(hoy, emparejar)
    actuales = [PartidoEu(p.fecha, emparejar(p.local), emparejar(p.visitante), p.gl, p.gv, True)
                for p in calendario if p.gl is not None]
    modelo = ModeloEuropeo().ajustar(dom + hist + actuales, hasta=hoy)
    for p in proximos:
        modelo.registrar(p.local, emparejar(p.local))
        modelo.registrar(p.visitante, emparejar(p.visitante))
        print(f"    {p.comp} {p.local} -> {emparejar(p.local)} | {p.visitante} -> {emparejar(p.visitante)}")
    return proximos, modelo
