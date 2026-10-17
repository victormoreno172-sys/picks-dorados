"""
Esports: Counter-Strike 2, Valorant y League of Legends (datos de bo3.gg, sin clave).

Modelo: cada equipo tiene una fuerza; la probabilidad de ganar un MAPA es
logística en la diferencia de fuerzas. Se aprende de los mapas ganados y
perdidos en los partidos del último año (lo reciente pesa más). Con la
probabilidad por mapa se calcula la serie (Bo1, Bo3, Bo5):
  - ganador
  - hándicap de mapas (-1.5 / +1.5 ...)
  - total de mapas
  - resultado exacto
Solo se muestran torneos de nivel S y A (los importantes), pero el modelo se
entrena también con los de nivel B para conocer a más equipos.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import comb
from zoneinfo import ZoneInfo

import numpy as np
import requests
from scipy.optimize import minimize

import config
from analisis import Analisis, Pick
from datos import PartidoProximo

URL = "https://api.bo3.gg/api/v1/matches"
CACHE = os.path.join(config.CARPETA_CACHE, "esports")
TZ = ZoneInfo(config.ZONA_HORARIA)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept": "application/json"}

JUEGOS = {  # código -> (nombre, id de bo3.gg, icono)
    "CS2": ("Counter-Strike 2", 1, "🎯"),
    "VAL": ("Valorant", 2, "🔫"),
    "LOL": ("League of Legends", 3, "🐉"),
}
UNIDAD = {"LOL": "partidas"}  # en LoL no hay mapas: se cuentan partidas
NIVELES_ENTRENAR = "s,a,b"
NIVELES_MOSTRAR = {"s", "a"}


@dataclass
class Serie:
    juego: str
    id: int
    fecha: date
    hora: str
    torneo: str
    nivel: str
    bo: int
    eq1: str
    eq2: str
    n1: str  # nombres para mostrar
    n2: str
    m1: int | None = None  # mapas ganados
    m2: int | None = None
    cuotas: dict | None = None
    img1: str = ""
    img2: str = ""


HIST: list = []
INFO: dict[tuple, dict] = {}


# ----------------------------------------------------------------- descarga
def _pagina(disc: int, estado: str, offset: int, orden: str) -> dict:
    params = {"page[offset]": offset, "page[limit]": 100, "sort": orden,
              "filter[matches.status][in]": estado, "filter[matches.discipline_id][eq]": disc,
              "filter[matches.tier][in]": NIVELES_ENTRENAR, "with": "teams,tournament"}
    for intento in range(3):
        try:
            r = requests.get(URL, params=params, headers=UA, timeout=40)
            if r.status_code == 429:
                time.sleep(15)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if intento == 2:
                print(f"  aviso esports: {e}")
            time.sleep(3)
    return {}


def _a_serie(juego: str, m: dict) -> Serie | None:
    try:
        dt = datetime.fromisoformat(m["start_date"]).astimezone(TZ)
        t1, t2 = m.get("team1") or {}, m.get("team2") or {}
        if not (m.get("team1_id") and m.get("team2_id")):
            return None
        hecho = m.get("status") == "finished"
        return Serie(juego, m["id"], dt.date(), dt.strftime("%H:%M"),
                     ((m.get("tournament") or {}).get("name") or "").strip(), m.get("tier") or "",
                     int(m.get("bo_type") or 1), f"{juego}-{m['team1_id']}", f"{juego}-{m['team2_id']}",
                     t1.get("name") or "?", t2.get("name") or "?",
                     int(m["team1_score"]) if hecho else None, int(m["team2_score"]) if hecho else None,
                     m.get("bet_updates") if isinstance(m.get("bet_updates"), dict) else None,
                     t1.get("image_url") or "", t2.get("image_url") or "")
    except (KeyError, ValueError, TypeError):
        return None


def historico(juego: str, hoy: date) -> list[Serie]:
    """Partidos terminados del último año. Se guardan y solo se piden los nuevos."""
    disc = JUEGOS[juego][1]
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, f"hist_{juego}.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            guardados = json.load(f)
    except (OSError, ValueError):
        guardados = {}
    limite = (hoy - timedelta(days=380)).isoformat()
    offset, nuevos = 0, 0
    while offset < 20000:
        d = _pagina(disc, "finished", offset, "-start_date")
        res = d.get("results") or []
        if not res:
            break
        ya = 0
        for m in res:
            if str(m["id"]) in guardados:
                ya += 1
            elif m.get("start_date", "") >= limite:
                guardados[str(m["id"])] = {k: m.get(k) for k in ("id", "start_date", "status", "tier", "bo_type",
                                                                   "team1_id", "team2_id", "team1_score",
                                                                   "team2_score")}
                guardados[str(m["id"])]["team1"] = {"name": (m.get("team1") or {}).get("name")}
                guardados[str(m["id"])]["team2"] = {"name": (m.get("team2") or {}).get("name")}
                nuevos += 1
        # Paramos al llegar a lo que ya teníamos o a partidos de hace más de un año
        if ya == len(res) or res[-1].get("start_date", "") < limite:
            break
        offset += 100
        time.sleep(0.5)
    guardados = {k: v for k, v in guardados.items() if v.get("start_date", "") >= limite}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(guardados, f)
    print(f"  {juego}: {len(guardados)} partidos de historial ({nuevos} nuevos)")
    return [s for s in (_a_serie(juego, m) for m in guardados.values()) if s and s.m1 is not None]


def proximos(juego: str, hoy: date, n_dias: int) -> list[Serie]:
    disc = JUEGOS[juego][1]
    out, offset = [], 0
    limite = hoy + timedelta(days=n_dias)
    while offset < 2000:
        d = _pagina(disc, "upcoming", offset, "start_date")
        res = d.get("results") or []
        for m in res:
            s = _a_serie(juego, m)
            if s and s.nivel in NIVELES_MOSTRAR and hoy <= s.fecha < limite and s.n1 != "?" and s.n2 != "?":
                out.append(s)
        if not res or (res and _a_serie(juego, res[-1]) and _a_serie(juego, res[-1]).fecha >= limite):
            break
        offset += 100
    if out and out[0].cuotas:
        print(f"  {juego}: ejemplo de cuotas en bo3.gg: {json.dumps(out[0].cuotas)[:300]}")
    return out


# ------------------------------------------------------------------- modelo
class ModeloMapas:
    def __init__(self, xi: float = 0.005, reg: float = 0.6):
        # xi: olvido por día (0.005 ≈ hace 4-5 meses pesa la mitad); los equipos cambian mucho
        self.xi, self.reg = xi, reg

    def ajustar(self, series: list[Serie], hasta: date) -> "ModeloMapas":
        ss = [s for s in series if s.fecha < hasta and (s.m1 or s.m2)]
        equipos = sorted({s.eq1 for s in ss} | {s.eq2 for s in ss})
        idx = {e: i for i, e in enumerate(equipos)}
        n = len(equipos)
        a = np.array([idx[s.eq1] for s in ss])
        b = np.array([idx[s.eq2] for s in ss])
        w1 = np.array([s.m1 for s in ss], float)
        w2 = np.array([s.m2 for s in ss], float)
        peso = np.exp(-self.xi * np.array([(hasta - s.fecha).days for s in ss], float))
        # Los torneos importantes pesan más
        peso *= np.array([{"s": 1.5, "a": 1.2}.get(s.nivel, 1.0) for s in ss])

        def f(r):
            z = r[a] - r[b]
            p = 1 / (1 + np.exp(-z))
            ll = peso * (w1 * np.log(p + 1e-12) + w2 * np.log(1 - p + 1e-12))
            g = peso * (w1 * (1 - p) - w2 * p)
            grad = -(np.bincount(a, g, n) - np.bincount(b, g, n)) + 2 * self.reg * r
            return -ll.sum() + self.reg * r @ r, grad

        res = minimize(f, np.zeros(n), jac=True, method="L-BFGS-B")
        self.fuerza = dict(zip(equipos, res.x))
        self.partidos = {e: 0 for e in equipos}
        for s in ss:
            self.partidos[s.eq1] += 1
            self.partidos[s.eq2] += 1
        print(f"  modelo esports: {n} equipos, {len(ss)} series")
        return self

    def conoce(self, eq: str) -> bool:
        return self.partidos.get(eq, 0) >= 6

    def p_mapa(self, eq1: str, eq2: str) -> float:
        # Se suaviza un poco: entre equipos parecidos hay mucha varianza por mapa
        z = 0.9 * (self.fuerza[eq1] - self.fuerza[eq2])
        return float(1 / (1 + np.exp(-z)))


def marcadores(p: float, bo: int) -> dict[tuple[int, int], float]:
    """Probabilidad de cada resultado final de la serie (mapas eq1, mapas eq2)."""
    k = bo // 2 + 1
    out = {}
    for perdidos in range(k):
        # eq1 gana el último mapa: k-1 ganados y `perdidos` perdidos antes, en cualquier orden
        out[(k, perdidos)] = comb(k - 1 + perdidos, perdidos) * p ** k * (1 - p) ** perdidos
        out[(perdidos, k)] = comb(k - 1 + perdidos, perdidos) * (1 - p) ** k * p ** perdidos
    return out


def mercados_serie(n1: str, n2: str, p: float, bo: int, unidad: str = "mapas") -> tuple[list[Pick], tuple[int, int], float]:
    m = marcadores(p, bo)
    k = bo // 2 + 1
    gana1 = sum(v for (a, b), v in m.items() if a == k)
    picks = [Pick(f"Gana {n1}", gana1), Pick(f"Gana {n2}", 1 - gana1)]
    if bo >= 3:
        for linea in [x + 0.5 for x in range(1, k)]:  # Bo3: 1.5 ; Bo5: 1.5, 2.5
            p1 = sum(v for (a, b), v in m.items() if a - b > linea)
            p2 = sum(v for (a, b), v in m.items() if b - a > linea)
            picks += [Pick(f"{n1} -{linea:g} {unidad}", p1), Pick(f"{n2} +{linea:g} {unidad}", 1 - p1),
                      Pick(f"{n2} -{linea:g} {unidad}", p2), Pick(f"{n1} +{linea:g} {unidad}", 1 - p2)]
        for linea in [x + 0.5 for x in range(k, bo)]:  # Bo3: 2.5 ; Bo5: 3.5, 4.5
            mas = sum(v for (a, b), v in m.items() if a + b > linea)
            picks += [Pick(f"Más de {linea:g} {unidad}", mas), Pick(f"Menos de {linea:g} {unidad}", 1 - mas)]
        for (a, b), v in sorted(m.items(), key=lambda kv: -kv[1]):
            picks.append(Pick(f"Resultado {n1} {a}-{b} {n2}", v))
    probable = max(m.items(), key=lambda kv: kv[1])
    return picks, probable[0], probable[1]


def _cuotas_ganador(s: Serie) -> tuple[float, float, str] | None:
    """Cuotas del ganador que trae bo3.gg (de una casa de apuestas, p. ej. Thunderpick)."""
    c = s.cuotas or {}
    try:
        c1, c2 = float(c["team_1"]["coeff"]), float(c["team_2"]["coeff"])
    except (KeyError, TypeError, ValueError):
        return None
    if c1 <= 1 or c2 <= 1:
        return None
    casa = "Thunderpick" if "thunderpick" in str(c.get("path", "")) else "casa de apuestas"
    return c1, c2, casa


def _p_mapa_para(gana: float, bo: int) -> float:
    """Probabilidad por mapa que da esa probabilidad de ganar la serie (búsqueda binaria)."""
    lo, hi = 1e-4, 1 - 1e-4
    k = bo // 2 + 1
    for _ in range(60):
        mid = (lo + hi) / 2
        g = sum(v for (x, y), v in marcadores(mid, bo).items() if x == k)
        lo, hi = (mid, hi) if g < gana else (lo, mid)
    return (lo + hi) / 2


def analizar_serie(s: Serie, modelo: ModeloMapas) -> Analisis | None:
    if not (modelo.conoce(s.eq1) and modelo.conoce(s.eq2)):
        return None
    p = modelo.p_mapa(s.eq1, s.eq2)
    cg = _cuotas_ganador(s)
    implicita = None
    if cg:  # mezcla con el mercado, como en fútbol
        c1, c2, casa = cg
        implicita = (1 / c1) / (1 / c1 + 1 / c2)
        k = s.bo // 2 + 1
        modelo_serie = sum(v for (x, y), v in marcadores(p, s.bo).items() if x == k)
        w = config.PESO_MERCADO_ESPORTS
        p = _p_mapa_para((1 - w) * modelo_serie + w * implicita, s.bo)
    unidad = UNIDAD.get(s.juego, "mapas")
    picks, (a, b), pm = mercados_serie(s.n1, s.n2, p, s.bo, unidad)
    if cg:
        for pk in picks:
            if pk.mercado == f"Gana {s.n1}":
                pk.cuota, pk.prob_cuota = cg[0], implicita
            elif pk.mercado == f"Gana {s.n2}":
                pk.cuota, pk.prob_cuota = cg[1], 1 - implicita
        # mapas y resultado exacto estimados (≈) desde la cuota del ganador
        from analisis import estimar_cuotas
        mkt, *_ = mercados_serie(s.n1, s.n2, _p_mapa_para(implicita, s.bo), s.bo, unidad)
        estimar_cuotas(picks, {k.mercado: k.prob for k in mkt}, 1 / cg[0] + 1 / cg[1] - 1)
    icono = JUEGOS[s.juego][2]
    liga = f"{icono} {s.juego} · {s.torneo or 'Torneo'}{' · Bo' + str(s.bo) if s.bo > 1 else ' · Bo1'}"
    partido = PartidoProximo(liga, s.fecha, s.hora, s.n1, s.n2, deporte="e", casa=cg[2] if cg else "")
    # "goles" esperados = mapas esperados de cada uno
    m = marcadores(p, s.bo)
    e1 = sum(x * v for (x, y), v in m.items())
    e2 = sum(y * v for (x, y), v in m.items())
    return Analisis(partido, e1, e2, f"{a}-{b}", pm, picks)


def analizar_dias(hoy: date, n_dias: int) -> dict[date, list[Analisis]]:
    salida: dict[date, list[Analisis]] = {}
    for juego in JUEGOS:
        try:
            hist = historico(juego, hoy)
            prox = proximos(juego, hoy, n_dias)
            print(f"  {juego}: {len(prox)} partidos de nivel S/A en los próximos {n_dias} días")
            if not prox or len(hist) < 100:
                continue
            modelo = ModeloMapas().ajustar(hist, hoy)
            HIST.extend(hist)
            for s in prox:
                INFO[(s.fecha.isoformat(), s.n1, s.n2)] = {"esc": [s.img1, s.img2], "estadio": s.torneo}
                a = analizar_serie(s, modelo)
                if a:
                    salida.setdefault(s.fecha, []).append(a)
                else:
                    print(f"    sin datos suficientes: {s.n1} - {s.n2}")
        except Exception as e:
            import traceback
            print(f"  aviso esports {juego}: {e}")
            traceback.print_exc()
    return salida
