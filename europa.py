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
    "fc basel": "Basel", "basel 1893": "Basel", "fcsb": "FCSB", "steaua bucuresti": "FCSB",
    "aek athens": "AEK", "aek": "AEK", "ofi": "OFI Crete", "ofi crete": "OFI Crete",
    "nec nijmegen": "Nijmegen", "nec": "Nijmegen",
    "internazionale milano": "Inter", "lazio roma": "Lazio", "sporting clube portugal": "Sp Lisbon",
    "istanbul basaksehir": "Buyuksehyr", "basaksehir": "Buyuksehyr",
    "rapid vienna": "Rapid Vienna", "rapid wien": "Rapid Vienna", "austria vienna": "Austria Vienna",
    "austria wien": "Austria Vienna", "rakow czestochowa": "Rakow", "jagiellonia bialystok": "Jagiellonia",
    "hjk helsinki": "HJK", "hjk": "HJK", "kups": "KuPS",
    "universitatea craiova": "U Craiova", "universitatea cluj": "U Cluj",
}
# Nombre en inglés -> nombre local (para equipos sin liga en nuestros datos)
ALIAS_SIN_LIGA = {
    "slavia prague": "slavia praha", "sparta prague": "sparta praha", "red star belgrade": "crvena zvezda",
    "fc red star belgrade": "crvena zvezda", "partizan belgrade": "partizan", "shakhtar": "shakhtar donetsk",
    "dynamo kyiv": "dynamo kyiv", "dynamo kiev": "dynamo kyiv", "plzen": "viktoria plzen",
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
        self.sin_liga: dict[str, str] = {}  # "~nombre" -> país (equipos sin liga en nuestros datos)
        self.conocidos = set(self.todos.values())

    def __call__(self, nombre: str, pais: str | None = None) -> str:
        clave = (nombre, pais)
        if clave not in self.cache:
            self.cache[clave] = self._buscar(nombre, pais)
        return self.cache[clave]

    @staticmethod
    def _contenido(n: str, candidatos, min_len: int = 0) -> str | None:
        """'Jagiellonia Bialystok' ~ 'Jagiellonia'. Solo si hay un único candidato."""
        tokens = set(n.split())
        enc = []
        for c in candidatos:
            ct = set(c.split())
            comunes = tokens & ct
            if c and (ct <= tokens or tokens <= ct) and any(len(t) >= min_len for t in comunes):
                enc.append(c)
        return enc[0] if len(enc) == 1 else None

    def _buscar(self, nombre: str, pais: str | None) -> str:
        import difflib
        pais = {"MCO": "FRA"}.get(pais, pais)  # el Mónaco juega la liga francesa
        n = normalizar(nombre)
        if n in ALIAS and ALIAS[n] in self.conocidos:
            return ALIAS[n]
        candidatos = self.por_pais.get(pais, {}) if pais else self.todos
        if n in candidatos:
            return candidatos[n]
        # Dentro de un país vale cualquier coincidencia; a nivel global se exige una
        # palabra larga en común (si no, "Inter Turku" acabaría siendo el Inter).
        c = self._contenido(n, candidatos, 0 if pais else 6)
        if c:
            return candidatos[c]
        m = difflib.get_close_matches(n, list(candidatos), n=1, cutoff=0.75 if pais else 0.86)
        if m:
            return candidatos[m[0]]
        # Equipo sin liga en nuestros datos: ¿ya apareció en partidos europeos con otro nombre?
        n = ALIAS_SIN_LIGA.get(n, n)
        if "~" + n in self.sin_liga:
            return "~" + n
        previos = [k[1:] for k in self.sin_liga if not pais or self.sin_liga[k] == pais]
        c = self._contenido(n, previos, 5)
        if not c:
            m = difflib.get_close_matches(n, previos, n=1, cutoff=0.8)
            c = m[0] if m else None
        if c:
            return "~" + c
        self.sin_liga["~" + n] = pais or "?"
        return "~" + n


# ------------------------------------------------------------------ datos
@dataclass
class PartidoEu:
    fecha: date
    local: str
    visitante: str
    gl: int
    gv: int
    europeo: bool
    liga: str = ""  # código de la liga (solo partidos nacionales)


def _historico_nuevo(codigo: str, desde: date) -> list[PartidoEu]:
    texto = datos._descargar(URL_NUEVAS.format(codigo=codigo), f"nuevo_{codigo}.csv", 12)
    out = []
    for f in csv.DictReader(io.StringIO(texto)):
        try:
            d = datos._fecha(f["Date"])
            if d >= desde and f.get("HG") not in (None, ""):
                out.append(PartidoEu(d, f["Home"].strip(), f["Away"].strip(), int(float(f["HG"])),
                                     int(float(f["AG"])), False, codigo))
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
                    lista = [PartidoEu(p.fecha, p.local, p.visitante, p.goles_local, p.goles_visitante,
                                       False, cod) for p in datos.historico(cod, hoy)]
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

    def ajustar(self, partidos: list[PartidoEu], hasta: date,
                pais_sin_liga: dict[str, str] | None = None) -> "ModeloEuropeo":
        """
        Fuerza de un equipo = nivel de su LIGA + lo que destaca dentro de ella.
        El nivel de cada liga se aprende de los partidos europeos entre países;
        así un equipo que arrasa en una liga floja no parece un gigante.
        """
        partidos = sorted((p for p in partidos if p.fecha < hasta), key=lambda p: p.fecha)
        equipos = sorted({p.local for p in partidos} | {p.visitante for p in partidos})
        idx = {e: i for i, e in enumerate(equipos)}
        n = len(equipos)

        # Liga de cada equipo: la de su partido nacional más reciente.
        liga_de: dict[str, str] = {}
        for p in partidos:
            if p.liga:
                liga_de[p.local] = liga_de[p.visitante] = p.liga
        for e in equipos:
            if e not in liga_de:
                liga_de[e] = "X-" + (pais_sin_liga or {}).get(e, "?")
        ligas = sorted(set(liga_de.values()))
        lidx = {l: i for i, l in enumerate(ligas)}
        nl = len(ligas)
        eq_liga = np.array([lidx[liga_de[e]] for e in equipos])

        h = np.array([idx[p.local] for p in partidos])
        a = np.array([idx[p.visitante] for p in partidos])
        lh, la = eq_liga[h], eq_liga[a]
        x = np.array([p.gl for p in partidos], dtype=float)
        y = np.array([p.gv for p in partidos], dtype=float)
        eu = np.array([p.europeo for p in partidos], dtype=float)
        w = np.exp(-self.xi * np.array([(hasta - p.fecha).days for p in partidos], dtype=float))
        w = w * np.where(eu > 0, 2.0, 1.0)  # los partidos europeos valen doble: son los que unen ligas
        reg_eq, reg_liga = 3.0, 0.3  # equipos con pocos datos -> media de su liga

        def f(theta):
            ta, td = theta[:n], theta[n:2 * n]
            ga, gd = theta[2 * n:2 * n + nl], theta[2 * n + nl:2 * n + 2 * nl]
            c0, hd, he = theta[2 * n + 2 * nl:]
            ll = ta[h] + ga[lh] + td[a] + gd[la] + c0 + hd * (1 - eu) + he * eu
            lm = ta[a] + ga[la] + td[h] + gd[lh] + c0
            lam, mu = np.exp(ll), np.exp(lm)
            nll = (-np.sum(w * (x * ll - lam + y * lm - mu))
                   + reg_eq * (ta @ ta + td @ td) + reg_liga * (ga @ ga + gd @ gd))
            r1, r2 = w * (x - lam), w * (y - mu)
            g_ta = -(np.bincount(h, r1, n) + np.bincount(a, r2, n)) + 2 * reg_eq * ta
            g_td = -(np.bincount(a, r1, n) + np.bincount(h, r2, n)) + 2 * reg_eq * td
            g_ga = -(np.bincount(lh, r1, nl) + np.bincount(la, r2, nl)) + 2 * reg_liga * ga
            g_gd = -(np.bincount(la, r1, nl) + np.bincount(lh, r2, nl)) + 2 * reg_liga * gd
            g = np.concatenate([g_ta, g_td, g_ga, g_gd,
                                [-(r1.sum() + r2.sum()), -np.sum(r1 * (1 - eu)), -np.sum(r1 * eu)]])
            return nll, g

        self._f = f
        res = minimize(f, np.zeros(2 * n + 2 * nl + 3), jac=True, method="L-BFGS-B",
                       options={"maxiter": 2000})
        t = res.x
        ga, gd = t[2 * n:2 * n + nl], t[2 * n + nl:2 * n + 2 * nl]
        self.equipos, self.liga_de = equipos, liga_de
        self.att = {e: t[i] + ga[eq_liga[i]] for i, e in enumerate(equipos)}
        self.dfn = {e: t[n + i] + gd[eq_liga[i]] for i, e in enumerate(equipos)}
        self.nivel_liga = {l: float(ga[i] - gd[i]) for l, i in lidx.items()}
        self.c0, self.campo_dom, self.campo_eu = t[2 * n + 2 * nl:]
        self.n_partidos = dict(zip(equipos, np.bincount(h, minlength=n) + np.bincount(a, minlength=n)))
        top = sorted(self.nivel_liga.items(), key=lambda kv: -kv[1])
        print(f"  modelo europeo: {n} equipos, {nl} ligas, {len(partidos)} partidos, "
              f"ventaja local en Europa {np.exp(self.campo_eu):.2f}x")
        print("  nivel de las ligas:", ", ".join(f"{l} {v:+.2f}" for l, v in top))
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
    sueltos = sorted(f"{p}:{k}" for k, p in emparejar.sin_liga.items() if p in LIGAS_PAIS or p == "?")
    print(f"  equipos sin emparejar ({len(sueltos)}): {', '.join(sueltos)}")
    modelo = ModeloEuropeo().ajustar(dom + hist + actuales, hasta=hoy, pais_sin_liga=emparejar.sin_liga)
    for p in proximos:
        modelo.registrar(p.local, emparejar(p.local))
        modelo.registrar(p.visitante, emparejar(p.visitante))
        print(f"    {p.comp} {p.local} -> {emparejar(p.local)} | {p.visitante} -> {emparejar(p.visitante)}")
    return proximos, modelo
