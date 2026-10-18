"""
Tenis: ATP y WTA (datos de ESPN; cuotas de Winamax cuando las hay).

Modelo Elo, como el de los análisis profesionales de tenis:
  - un Elo general por jugador y otro por superficie (tierra, dura, hierba);
  - la fuerza para un partido es la media de los dos;
  - la K (lo que se mueve el Elo tras cada partido) es mayor para jugadores con
    pocos partidos y menor para los consolidados.
Con la probabilidad de ganar el partido se deduce la de ganar un set y de ahí:
ganador, resultado en sets, total de sets y hándicap de sets (al mejor de 3 o de 5).
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config
from analisis import Analisis, Pick
from datos import PartidoProximo

URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard"
CACHE = os.path.join(config.CARPETA_CACHE, "tenis")
TZ = ZoneInfo(config.ZONA_HORARIA)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
TOURS = {"ATP": "atp", "WTA": "wta"}

TIERRA = ("roland garros", "french open", "madrid", "rome", "roma", "internazionali", "monte carlo", "monte-carlo",
          "barcelona", "hamburg", "estoril", "munich", "geneva", "lyon", "bastad", "båstad", "gstaad", "umag",
          "kitzbuhel", "kitzbühel", "buenos aires", "rio", "santiago", "cordoba", "córdoba", "houston", "marrakech",
          "bucharest", "parma", "palermo", "prague", "rabat", "strasbourg", "charleston", "bogota", "bogotá",
          "portoroz", "lausanne", "iasi", "budapest", "warsaw", "bad homburg", "cluj", "istanbul")
HIERBA = ("wimbledon", "halle", "queen", "hertogenbosch", "eastbourne", "newport", "mallorca", "stuttgart",
          "nottingham", "birmingham", "berlin", "bad homburg")


def superficie(torneo: str, fecha: date) -> str:
    n = torneo.lower()
    if any(h in n for h in HIERBA) and fecha.month in (6, 7):
        return "hierba"
    if any(t in n for t in TIERRA) and fecha.month in (2, 3, 4, 5, 6, 7, 8, 9):
        return "tierra"
    return "dura"


@dataclass
class Partido:
    tour: str
    id: str
    fecha: date
    hora: str
    torneo: str
    ronda: str
    sets_max: int
    j1: str
    j2: str
    n1: str
    n2: str
    gana1: bool | None = None  # None = no jugado
    s1: int | None = None      # sets ganados
    s2: int | None = None
    retirada: bool = False
    flag1: str = ""   # banderas y sede (para la ficha del partido)
    flag2: str = ""
    sede: str = ""


# --------------------------------------------------------------- descarga
def _get(tour: str, dia: date | None, horas: float | None):
    os.makedirs(CACHE, exist_ok=True)
    # v2: desde que se separan los cuadros masculino y femenino (la caché vieja los mezclaba)
    nombre = f"v2_{tour}_{dia:%Y%m%d}.json" if dia else f"v2_{tour}_actual.json"
    ruta = os.path.join(CACHE, nombre)
    if os.path.exists(ruta) and (horas is None or time.time() - os.path.getmtime(ruta) < horas * 3600):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    try:
        r = requests.get(URL.format(tour=TOURS[tour]), headers=UA, timeout=60,
                         params={"dates": f"{dia:%Y%m%d}"} if dia else None)
        r.raise_for_status()
        partidos = [p.__dict__ for p in _parsear(tour, r.json())]
        for p in partidos:
            p["fecha"] = p["fecha"].isoformat()
    except (requests.RequestException, ValueError) as e:
        print(f"  aviso tenis {tour}: {e}")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
        return []
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(partidos, f)  # solo lo necesario (la respuesta original pesa mucho)
    return partidos


GRAND_SLAMS = ("australian open", "roland garros", "french open", "wimbledon", "us open")


def es_grand_slam(tour: str, torneo: str) -> bool:
    """Al mejor de 5 sets solo juegan los hombres en los Grand Slam (ESPN marca 5 en todo el ATP)."""
    t = torneo.lower()
    return tour == "ATP" and any(g in t for g in GRAND_SLAMS)


def _parsear(tour: str, datos: dict) -> list[Partido]:
    out = []
    for ev in (datos or {}).get("events", []):
        torneo = ev.get("name") or ""
        for g in ev.get("groupings") or []:
            gn = ((g.get("grouping") or {}).get("displayName") or "").lower()
            if "single" not in gn:
                continue
            # En los torneos combinados ESPN mete los dos cuadros en cada circuito: cada uno con el suyo
            if (tour == "ATP" and "women" in gn) or (tour == "WTA" and "women" not in gn and "men" in gn):
                continue
            for c in g.get("competitions") or []:
                try:
                    jug = c["competitors"]
                    if len(jug) != 2 or not all(x.get("athlete") for x in jug):
                        continue
                    dt = datetime.fromisoformat(c["date"].replace("Z", "+00:00")).astimezone(TZ)
                    est = (c.get("status") or {}).get("type") or {}
                    a, b = jug
                    hecho = bool(est.get("completed"))
                    sa = sum(1 for x, y in zip(a.get("linescores") or [], b.get("linescores") or [])
                             if (x.get("value") or 0) > (y.get("value") or 0))
                    sb = sum(1 for x, y in zip(a.get("linescores") or [], b.get("linescores") or [])
                             if (y.get("value") or 0) > (x.get("value") or 0))
                    sets_max = int(((c.get("format") or {}).get("regulation") or {}).get("periods") or 3)
                    if hecho and not (a.get("winner") or b.get("winner")):
                        continue  # sin ganador claro (walkover raro): fuera
                    out.append(Partido(
                        tour, str(c.get("id")), dt.date(), dt.strftime("%H:%M"), torneo,
                        (c.get("round") or {}).get("displayName") or "", 5 if sets_max >= 5 and es_grand_slam(tour, torneo) else 3,
                        f"{tour}-{a['athlete'].get('id') or a['athlete'].get('displayName')}",
                        f"{tour}-{b['athlete'].get('id') or b['athlete'].get('displayName')}",
                        a["athlete"].get("displayName") or "?", b["athlete"].get("displayName") or "?",
                        bool(a.get("winner")) if hecho else None, sa if hecho else None, sb if hecho else None,
                        est.get("name") in ("STATUS_RETIRED", "STATUS_WALKOVER"),
                        (a["athlete"].get("flag") or {}).get("href") or "", (b["athlete"].get("flag") or {}).get("href") or "",
                        ", ".join(x for x in ((c.get("venue") or {}).get("fullName"), (c.get("venue") or {}).get("court")) if x)))
                except (KeyError, TypeError, ValueError):
                    continue
    return out


def _cargar(lista: list[dict]) -> list[Partido]:
    out = []
    for d in lista:
        d = dict(d)
        d["fecha"] = date.fromisoformat(d["fecha"])
        p = Partido(**d)
        if p.sets_max == 5 and not es_grand_slam(p.tour, p.torneo):  # caché guardada antes del arreglo
            p.sets_max = 3
        out.append(p)
    return out


def historico(tour: str, hoy: date) -> list[Partido]:
    """Último año: se pide un día de cada tres (cada torneo dura una o dos semanas)."""
    vistos: dict[str, Partido] = {}
    d = hoy - timedelta(days=372)
    while d < hoy:
        pasado = d < hoy - timedelta(days=16)  # torneos ya terminados no cambian
        for p in _cargar(_get(tour, d, None if pasado else 8)):
            if p.gana1 is not None:
                vistos[p.id] = p
        d += timedelta(days=3)
    for p in _cargar(_get(tour, None, 2)):
        if p.gana1 is not None:
            vistos[p.id] = p
    return sorted(vistos.values(), key=lambda p: p.fecha)


def proximos(tour: str, hoy: date, n_dias: int) -> list[Partido]:
    vistos = {}
    for k in range(-1, n_dias):
        dia = hoy + timedelta(days=k)
        for p in _cargar(_get(tour, dia if k > 0 else None, 2)):
            if p.gana1 is None and hoy <= p.fecha < hoy + timedelta(days=n_dias) and "?" not in (p.n1, p.n2) \
                    and "TBD" not in (p.n1 + p.n2):
                vistos[p.id] = p
    return sorted(vistos.values(), key=lambda p: (p.fecha, p.hora))


# ----------------------------------------------------------------- modelo
# Parámetros calibrados con el último año (calibracion/backtest_tenis.py):
#   a, e = tamaño del ajuste tras cada partido (a / (partidos + 5) ** e)
#   w_sup = peso del Elo de la superficie frente al general
#   t = temperatura: multiplica el logit (por debajo de 1 = el modelo se pasaba de seguro)
PARAMS = {"ATP": {"a": 150, "e": 0.5, "w_sup": 0.25, "t": 1.0},
          "WTA": {"a": 250, "e": 0.5, "w_sup": 0.25, "t": 0.8}}
# Los sets no son independientes: quien gana un set tiene más opciones de ganar el siguiente.
# Con sets independientes el modelo daba ~49 % de partidos a 3 sets y en realidad son ~37 %.
RHO_SETS = 0.2


class EloTenis:
    def __init__(self, tour: str = "ATP"):
        pr = PARAMS.get(tour, PARAMS["ATP"])
        self.a, self.e, self.w_sup, self.t = pr["a"], pr["e"], pr["w_sup"], pr["t"]
        self.general: dict[str, float] = {}
        self.sup: dict[tuple[str, str], float] = {}
        self.n: dict[str, int] = {}
        self.n_sup: dict[tuple[str, str], int] = {}

    def _k(self, n: int) -> float:
        return self.a / (n + 5) ** self.e

    @staticmethod
    def _esperado(a: float, b: float) -> float:
        return 1 / (1 + 10 ** ((b - a) / 400))

    def ajustar(self, partidos: list[Partido]) -> "EloTenis":
        for p in partidos:
            s = superficie(p.torneo, p.fecha)
            g1, g2 = self.general.get(p.j1, 1500), self.general.get(p.j2, 1500)
            e = self._esperado(g1, g2)
            r = 1.0 if p.gana1 else 0.0
            if p.retirada:  # un abandono dice poco: cuenta la mitad
                r = 0.5 + (r - 0.5) * 0.5
            n1, n2 = self.n.get(p.j1, 0), self.n.get(p.j2, 0)
            self.general[p.j1] = g1 + self._k(n1) * (r - e)
            self.general[p.j2] = g2 + self._k(n2) * ((1 - r) - (1 - e))
            self.n[p.j1], self.n[p.j2] = n1 + 1, n2 + 1
            k1, k2 = (p.j1, s), (p.j2, s)
            s1, s2 = self.sup.get(k1, 1500), self.sup.get(k2, 1500)
            es = self._esperado(s1, s2)
            ns1, ns2 = self.n_sup.get(k1, 0), self.n_sup.get(k2, 0)
            self.sup[k1] = s1 + self._k(ns1) * (r - es)
            self.sup[k2] = s2 + self._k(ns2) * ((1 - r) - (1 - es))
            self.n_sup[k1], self.n_sup[k2] = ns1 + 1, ns2 + 1
        print(f"  modelo tenis: {len(self.general)} jugadores, {len(partidos)} partidos")
        return self

    def conoce(self, j: str) -> bool:
        return self.n.get(j, 0) >= 8

    def p_partido(self, j1: str, j2: str, sup: str) -> float:
        g1, g2 = self.general.get(j1, 1500), self.general.get(j2, 1500)
        a = (1 - self.w_sup) * g1 + self.w_sup * self.sup.get((j1, sup), g1)
        b = (1 - self.w_sup) * g2 + self.w_sup * self.sup.get((j2, sup), g2)
        p = self._esperado(a, b)
        z = math.log(p / (1 - p)) * self.t
        return 1 / (1 + math.exp(-z))


# --------------------------------------------------------------- mercados
def marcadores_sets(s: float, sets_max: int, rho: float = RHO_SETS) -> dict[tuple[int, int], float]:
    """Probabilidad de cada resultado en sets. s = ganar el primer set; después de ganar un set
    la probabilidad del siguiente sube (s + rho·(1-s)) y después de perderlo baja (s·(1-rho))."""
    k = sets_max // 2 + 1
    out: dict[tuple[int, int], float] = {}

    def rec(a, b, prev, pr):
        if a == k or b == k:
            out[(a, b)] = out.get((a, b), 0) + pr
            return
        q = s if prev is None else (s + rho * (1 - s) if prev == 1 else s * (1 - rho))
        rec(a + 1, b, 1, pr * q)
        rec(a, b + 1, 2, pr * (1 - q))
    rec(0, 0, None, 1.0)
    return out


def p_partido_desde_set(s: float, sets_max: int = 3, rho: float = RHO_SETS) -> float:
    k = sets_max // 2 + 1
    return sum(v for (a, b), v in marcadores_sets(s, sets_max, rho).items() if a == k)


def p_set_desde_partido(p: float, sets_max: int = 3, rho: float = RHO_SETS) -> float:
    """El Elo predice partidos al mejor de 3: se deduce la probabilidad de ganar el primer set."""
    lo, hi = 1e-4, 1 - 1e-4
    for _ in range(60):
        s = (lo + hi) / 2
        lo, hi = (s, hi) if p_partido_desde_set(s, sets_max, rho) < p else (lo, s)
    return (lo + hi) / 2


def mercados_tenis(n1: str, n2: str, p_bo3: float, sets_max: int):
    from esports import mercados_serie
    s = p_set_desde_partido(p_bo3)
    picks, (a, b), pm = mercados_serie(n1, n2, s, sets_max, dist=marcadores_sets(s, sets_max))
    for pk in picks:  # mismos mercados que esports, pero en sets
        pk.mercado = pk.mercado.replace(" mapas", " sets")
    return picks, (a, b), pm, s


def analizar(p: Partido, elo: EloTenis, hoy: date) -> Analisis | None:
    if not (elo.conoce(p.j1) and elo.conoce(p.j2)):
        return None
    sup = superficie(p.torneo, p.fecha)
    prob = elo.p_partido(p.j1, p.j2, sup)
    cuotas, casa = {}, ""
    try:  # cuotas de Winamax (ganador) si las hay
        import cuotas as cmod
        ev = cmod.instancia(hoy).buscar(p.tour, p.fecha, p.n1, p.n2)
        if ev and f"Gana local" in ev.cuotas and "Gana visitante" in ev.cuotas:
            c1, c2 = ev.cuotas["Gana local"], ev.cuotas["Gana visitante"]
            imp = (1 / c1) / (1 / c1 + 1 / c2)
            w = config.PESO_MERCADO
            # se mezcla en la escala del partido al mejor de 3 (la del Elo)
            if p.sets_max == 5:
                # pasar la implícita (al mejor de 5) a la escala del mejor de 3
                imp = p_partido_desde_set(p_set_desde_partido(imp, 5), 3)
            prob = (1 - w) * prob + w * imp
            cuotas = {f"Gana {p.n1}": c1, f"Gana {p.n2}": c2}
            casa = ev.casa
    except Exception as e:
        print(f"  aviso cuotas tenis: {e}")
    picks, (a, b), pm, s = mercados_tenis(p.n1, p.n2, prob, p.sets_max)
    for pk in picks:
        if pk.mercado in cuotas:
            pk.cuota = cuotas[pk.mercado]
            otro = [v for k, v in cuotas.items() if k != pk.mercado][0]
            pk.prob_cuota = (1 / pk.cuota) / (1 / pk.cuota + 1 / otro)
    if cuotas:  # sets, hándicap y resultado exacto estimados (≈) desde la cuota del ganador
        from analisis import estimar_cuotas
        mkt_picks, *_ = mercados_tenis(p.n1, p.n2, imp, p.sets_max)
        c1, c2 = cuotas[f"Gana {p.n1}"], cuotas[f"Gana {p.n2}"]
        estimar_cuotas(picks, {k.mercado: k.prob for k in mkt_picks}, 1 / c1 + 1 / c2 - 1)
    icono = "🎾"
    sup_txt = {"tierra": "tierra", "dura": "dura", "hierba": "hierba"}[sup]
    liga = f"{icono} {p.tour} · {p.torneo} · {sup_txt}"
    partido = PartidoProximo(liga, p.fecha, p.hora, p.n1, p.n2, deporte="te", casa=casa)
    m = marcadores_sets(s, p.sets_max)
    e1 = sum(x * v for (x, y), v in m.items())
    e2 = sum(y * v for (x, y), v in m.items())
    return Analisis(partido, e1, e2, f"{a}-{b}", pm, picks)


HIST: list = []   # partidos jugados (para "últimos partidos" en la ficha)
INFO: dict[tuple, dict] = {}
ELO: dict[str, "EloTenis"] = {}   # modelo de cada circuito (para el ranking de la pestaña Ligas)
PROX: list = []                    # próximos partidos (para los torneos de la pestaña Ligas)


def analizar_dias(hoy: date, n_dias: int) -> dict[date, list[Analisis]]:
    salida: dict[date, list[Analisis]] = {}
    import historial
    for tour in TOURS:
        try:
            hist = historico(tour, hoy)
            HIST.extend(hist)
            for h in hist:
                historial.anotar(h.fecha, h.n1, h.n2, h.s1 or 0, h.s2 or 0)
            prox = proximos(tour, hoy, n_dias)
            PROX.extend(prox)
            print(f"  {tour}: {len(hist)} partidos de historial, {len(prox)} próximos")
            if len(hist) < 300 or not prox:
                continue
            elo = EloTenis(tour).ajustar(hist)
            ELO[tour] = elo
            for p in prox:
                INFO[(p.fecha.isoformat(), p.n1, p.n2)] = {"esc": [p.flag1, p.flag2], "estadio": p.sede or p.torneo}
                a = analizar(p, elo, hoy)
                if a:
                    salida.setdefault(p.fecha, []).append(a)
        except Exception as e:
            import traceback
            print(f"  aviso tenis {tour}: {e}")
            traceback.print_exc()
    return salida
