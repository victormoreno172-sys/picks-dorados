"""
Baloncesto: NBA, Euroliga, Eurocup, Basketball Champions League y las mejores
ligas europeas.

Modelo: cada equipo tiene un rating de ATAQUE (puntos que mete por encima de la
media) y de DEFENSA (puntos que encaja). Con eso se calculan los puntos
esperados de cada equipo; el margen y el total siguen una distribución normal
cuya dispersión se mide con los partidos reales. De ahí salen:
  - ganador
  - hándicap (varias líneas)
  - total de puntos (varias líneas)
Las ligas europeas se entrenan juntas: los equipos de Euroliga/Eurocup/BCL que
también juegan su liga nacional conectan el nivel de todas ellas.

Fuentes (gratis):
  - NBA: ESPN (resultados y líneas de las casas)
  - Europa: TheSportsDB, jornada a jornada (mismos ids de equipo en todas las competiciones)
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import requests
from scipy import sparse
from scipy.sparse.linalg import lsqr
from scipy.stats import norm

import config
from analisis import Analisis, Pick
from datos import PartidoProximo

TZ = ZoneInfo(config.ZONA_HORARIA)
CACHE = os.path.join(config.CARPETA_CACHE, "basket")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

URL_ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={dia}"
URL_TSDB = "https://www.thesportsdb.com/api/v1/json/{clave}/"

# ESPN usa algunas abreviaturas distintas de las oficiales de la NBA
ESPN_A_NBA = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS", "PHO": "PHX"}

CUOTA_ESTANDAR = 1.91  # las líneas de hándicap/total suelen pagarse a -110 (1.91)


@dataclass
class Juego:
    comp: str
    fecha: date
    hora: str
    local_id: str
    visit_id: str
    local: str
    visitante: str
    pl: int | None = None   # puntos local (None si no se ha jugado)
    pv: int | None = None
    spread_local: float | None = None  # línea de la casa (negativo = local favorito)
    total_casa: float | None = None
    cuotas: dict = None  # cuotas reales (Winamax) por mercado
    casa: str = ""

    @property
    def jugado(self) -> bool:
        return self.pl is not None and self.pv is not None


# ------------------------------------------------------------------- caché
def _cache_json(nombre: str, url: str, horas: float | None, params=None, pausa: float = 0.0):
    """Descarga JSON con caché en disco. horas=None -> no caduca nunca."""
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, nombre)
    if os.path.exists(ruta) and (horas is None or time.time() - os.path.getmtime(ruta) < horas * 3600):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    for intento in range(3):
        try:
            r = requests.get(url, timeout=40, headers=UA, params=params)
            if r.status_code == 429:
                time.sleep(25)
                continue
            r.raise_for_status()
            datos = r.json()
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(datos, f)
            if pausa:
                time.sleep(pausa)
            return datos
        except (requests.RequestException, ValueError) as e:
            if intento == 2:
                print(f"  aviso baloncesto: {url[:90]} -> {e}")
            time.sleep(3)
    if os.path.exists(ruta):  # mejor un dato viejo que ninguno
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return None


# --------------------------------------------------------------------- NBA
def _temporada_nba(hoy: date) -> int:
    return hoy.year if hoy.month >= 8 else hoy.year - 1


def nba_temporada_pasada(hoy: date) -> list[Juego]:
    """Resultados de la temporada pasada, día a día desde ESPN (se guardan para siempre)."""
    anio = _temporada_nba(hoy) - 1
    out, d = [], date(anio, 10, 15)
    while d <= date(anio + 1, 6, 25):
        datos = _cache_json(f"espn_{d:%Y%m%d}.json", URL_ESPN.format(dia=f"{d:%Y%m%d}"), None)
        out += [j for j in _parse_espn(datos) if j.jugado]
        d += timedelta(days=1)
    return out


def _parse_espn(datos: dict) -> list[Juego]:
    out = []
    for e in (datos or {}).get("events", []):
        if (e.get("season") or {}).get("type") not in (2, 3):  # 2 = regular, 3 = playoffs
            continue
        c = e["competitions"][0]
        eq = {t["homeAway"]: t for t in c["competitors"]}
        if "home" not in eq or "away" not in eq:
            continue
        dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(TZ)
        ab = {k: ESPN_A_NBA.get(t["team"]["abbreviation"], t["team"]["abbreviation"]) for k, t in eq.items()}
        hecho = c.get("status", {}).get("type", {}).get("completed", False)
        j = Juego("NBA", dt.date(), dt.strftime("%H:%M"), "NBA-" + ab["home"], "NBA-" + ab["away"],
                  eq["home"]["team"]["displayName"], eq["away"]["team"]["displayName"],
                  int(eq["home"]["score"]) if hecho else None, int(eq["away"]["score"]) if hecho else None)
        odds = (c.get("odds") or [{}])[0]
        if odds.get("overUnder"):
            j.total_casa = float(odds["overUnder"])
        m = re.match(r"([A-Z]+)\s+(-?\d+(?:\.\d+)?)", odds.get("details") or "")
        if m:
            fav = ESPN_A_NBA.get(m.group(1), m.group(1))
            linea = -abs(float(m.group(2)))
            j.spread_local = linea if fav == ab["home"] else -linea
        elif (odds.get("details") or "").upper() == "EVEN":
            j.spread_local = 0.0
        out.append(j)
    return out


def nba_temporada_actual(hoy: date, n_dias: int) -> list[Juego]:
    inicio = date(_temporada_nba(hoy), 10, 1)
    out, d = [], inicio
    while d < hoy + timedelta(days=n_dias):
        pasado = d < hoy - timedelta(days=1)
        datos = _cache_json(f"espn_{d:%Y%m%d}.json", URL_ESPN.format(dia=f"{d:%Y%m%d}"),
                            None if pasado else 2)
        out += _parse_espn(datos)
        d += timedelta(days=1)
    return out


# ------------------------------------------------------------ Europa (TSDB)
def _temporadas_europa(hoy: date) -> list[str]:
    a = hoy.year if hoy.month >= 8 else hoy.year - 1
    return [f"{a - 1}-{a}", f"{a}-{a + 1}"]


def _evento_a_juego(comp: str, e: dict) -> Juego | None:
    if not e.get("idHomeTeam") or not e.get("idAwayTeam"):
        return None
    ts = e.get("strTimestamp")
    if ts:
        dt = datetime.fromisoformat(ts.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC")).astimezone(TZ)
        fecha, hora = dt.date(), dt.strftime("%H:%M")
    elif e.get("dateEvent"):
        fecha, hora = date.fromisoformat(e["dateEvent"]), ""
    else:
        return None
    pl, pv = e.get("intHomeScore"), e.get("intAwayScore")
    jugado = pl not in (None, "") and pv not in (None, "") and e.get("strStatus") not in ("NS", "Postponed")
    return Juego(comp, fecha, hora, "T" + e["idHomeTeam"], "T" + e["idAwayTeam"], e["strHomeTeam"],
                 e["strAwayTeam"], int(pl) if jugado else None, int(pv) if jugado else None)


def europa(hoy: date, n_dias: int) -> list[Juego]:
    clave = config.THESPORTSDB_KEY or "123"
    base = URL_TSDB.format(clave=clave)
    limite = hoy + timedelta(days=n_dias + 1)
    juegos: dict[str, Juego] = {}
    for comp, (_, lid) in config.BASKET_EUROPA.items():
        for temp in _temporadas_europa(hoy):
            vacias = 0
            for r in range(1, 61):
                nombre = f"tsdb_{lid}_{temp}_{r}.json"
                ruta = os.path.join(CACHE, nombre)
                # Una jornada ya terminada no cambia: se guarda para siempre.
                permanente = ruta + ".fin"
                if os.path.exists(permanente):
                    with open(permanente, encoding="utf-8") as f:
                        datos = json.load(f)
                else:
                    datos = _cache_json(nombre, base + f"eventsround.php?id={lid}&r={r}&s={temp}", 6, pausa=2.1)
                eventos = (datos or {}).get("events") or []
                if not eventos:
                    vacias += 1
                    if vacias >= 2:
                        break
                    continue
                vacias = 0
                lista = [j for j in (_evento_a_juego(comp, e) for e in eventos) if j]
                for e, j in zip(eventos, lista):
                    juegos[e["idEvent"]] = j
                if lista and all(j.jugado or j.fecha < hoy - timedelta(days=4) for j in lista):
                    if not os.path.exists(permanente):
                        with open(permanente, "w", encoding="utf-8") as f:
                            json.dump(datos, f)
                if lista and min(j.fecha for j in lista) > limite:
                    break  # jornadas más allá de la ventana: no hacen falta
        # Complemento por días (playoffs y jornadas con numeración rara)
        for k in range(n_dias):
            d = hoy + timedelta(days=k)
            datos = _cache_json(f"tsdbday_{lid}_{d}.json", base + f"eventsday.php?d={d}&l={lid}", 3, pausa=2.1)
            for e in (datos or {}).get("events") or []:
                j = _evento_a_juego(comp, e)
                if j:
                    juegos[e["idEvent"]] = j
    return list(juegos.values())


# ------------------------------------------------------------------ modelo
class ModeloBaloncesto:
    def __init__(self, xi: float = 0.004, reg: float = 4.0):
        # xi: olvido por día (0.004 ≈ un partido de hace 6 meses pesa la mitad)
        self.xi, self.reg = xi, reg

    def ajustar(self, juegos: list[Juego], hasta: date) -> "ModeloBaloncesto":
        js = [j for j in juegos if j.jugado and j.fecha < hasta]
        if len(js) < 50:
            raise ValueError(f"pocos partidos de baloncesto ({len(js)})")
        equipos = sorted({j.local_id for j in js} | {j.visit_id for j in js})
        comps = sorted({j.comp for j in js})
        ie, ic = {e: i for i, e in enumerate(equipos)}, {c: i for i, c in enumerate(comps)}
        n, nc, m = len(equipos), len(comps), len(js)
        w = np.exp(-self.xi * np.array([(hasta - j.fecha).days for j in js], float))
        # media de puntos de cada competición (ritmo de juego y reglas: NBA 48 min, FIBA 40)
        pts = np.array([[j.pl, j.pv] for j in js], float)
        cidx = np.array([ic[j.comp] for j in js])
        media = np.array([np.average(pts[cidx == k].mean(1), weights=w[cidx == k]) for k in range(nc)])
        # Incógnitas: ataque[n], defensa[n], ventaja local por competición[nc]
        filas, cols, vals, y, ww = [], [], [], [], []
        for r, j in enumerate(js):
            h, a, c = ie[j.local_id], ie[j.visit_id], ic[j.comp]
            # puntos local = media + ataque_local + defensa_visitante + ventaja_local
            filas += [2 * r] * 3; cols += [h, n + a, 2 * n + c]; vals += [1, 1, 1]
            # puntos visitante = media + ataque_visitante + defensa_local
            filas += [2 * r + 1] * 2; cols += [a, n + h]; vals += [1, 1]
            y += [j.pl - media[c], j.pv - media[c]]
            ww += [w[r], w[r]]
        sw = np.sqrt(np.array(ww))
        A = sparse.csr_matrix((vals, (filas, cols)), shape=(2 * m, 2 * n + nc))
        A = sparse.diags(sw) @ A
        b = np.array(y) * sw
        # regularización: un equipo con pocos partidos se queda cerca de la media
        sol = lsqr(A, b, damp=np.sqrt(self.reg), atol=1e-10, btol=1e-10, iter_lim=5000)[0]
        self.ataque = dict(zip(equipos, sol[:n]))
        self.defensa = dict(zip(equipos, sol[n:2 * n]))
        self.local = dict(zip(comps, sol[2 * n:]))
        self.media = dict(zip(comps, media))
        self.n_partidos = {e: 0 for e in equipos}
        for j in js:
            self.n_partidos[j.local_id] += 1
            self.n_partidos[j.visit_id] += 1
        # Dispersión real del margen y del total (residuos ponderados, últimos partidos)
        pred = A @ sol / sw
        res = (np.array(y) - pred).reshape(-1, 2)
        wm = w / w.sum()
        self.sd_margen = float(np.sqrt(np.sum(wm * (res[:, 0] - res[:, 1]) ** 2))) * 1.05
        self.sd_total = float(np.sqrt(np.sum(wm * (res[:, 0] + res[:, 1]) ** 2))) * 1.05
        self.comps = comps
        print(f"  modelo baloncesto {'/'.join(comps)}: {n} equipos, {m} partidos, "
              f"dispersión margen {self.sd_margen:.1f}, total {self.sd_total:.1f}")
        return self

    def conoce(self, equipo_id: str) -> bool:
        return self.n_partidos.get(equipo_id, 0) >= 5

    def esperado(self, j: Juego) -> tuple[float, float]:
        mu = self.media.get(j.comp, np.mean(list(self.media.values())))
        hl = self.local.get(j.comp, np.mean(list(self.local.values())))
        pl = mu + self.ataque[j.local_id] + self.defensa[j.visit_id] + hl
        pv = mu + self.ataque[j.visit_id] + self.defensa[j.local_id]
        return float(pl), float(pv)


# ---------------------------------------------------------------- mercados
LINEAS_HANDICAP = (2.5, 5.5, 8.5, 12.5)


def mercados_baloncesto(margen: float, total: float, sd_m: float, sd_t: float,
                        spread_casa: float | None = None, total_casa: float | None = None,
                        total_tipico: float | None = None) -> list[Pick]:
    """
    margen = puntos local - puntos visitante esperados.
    Las líneas son fijas (no dependen de la predicción), como en una casa de
    apuestas: así el porcentaje de cada línea refleja de verdad cada partido.
    """
    picks = []
    p_local = float(norm.sf(0, loc=margen, scale=sd_m))
    picks += [Pick("Gana local", p_local), Pick("Gana visitante", 1 - p_local)]

    lineas_h = set(LINEAS_HANDICAP)
    fav, dog = ("local", "visitante") if margen >= 0 else ("visitante", "local")
    s = 1 if margen >= 0 else -1
    for l in sorted(lineas_h):
        p = float(norm.sf(l, loc=s * margen, scale=sd_m))  # el favorito gana por más de l
        picks += [Pick(f"Hándicap {fav} -{l:g}", p), Pick(f"Hándicap {dog} +{l:g}", 1 - p)]
    if spread_casa is not None:
        l = abs(spread_casa)
        fav_c, dog_c, sc = (("local", "visitante", 1) if spread_casa <= 0 else ("visitante", "local", -1))
        p = float(norm.sf(l, loc=sc * margen, scale=sd_m))
        nombres = {pk.mercado for pk in picks}
        for nombre, prob in ((f"Hándicap {fav_c} -{l:g}", p), (f"Hándicap {dog_c} +{l:g}", 1 - p)):
            picks = [pk for pk in picks if pk.mercado != nombre]
            picks.append(Pick(nombre, prob, CUOTA_ESTANDAR, 0.5, estimada=True))

    base = 5 * round((total_tipico or total) / 5)  # total típico de la competición
    lineas_t = [base + d + 0.5 for d in (-15, -10, -5, 0, 5, 10, 15) if abs(base + d - total) <= 16]
    for t in lineas_t:
        p = float(norm.sf(t, loc=total, scale=sd_t))
        picks += [Pick(f"Más de {t:g} puntos", p), Pick(f"Menos de {t:g} puntos", 1 - p)]
    if total_casa is not None:
        t = total_casa
        p = float(norm.sf(t, loc=total, scale=sd_t))
        for nombre, prob in ((f"Más de {t:g} puntos", p), (f"Menos de {t:g} puntos", 1 - p)):
            picks = [pk for pk in picks if pk.mercado != nombre]
            picks.append(Pick(nombre, prob, CUOTA_ESTANDAR, 0.5, estimada=True))
    return picks


def _contrario(mercado: str) -> str | None:
    """Mercado opuesto de la misma línea (para quitar el margen de la casa)."""
    import re
    if mercado in ("Gana local", "Gana visitante"):
        return "Gana visitante" if mercado == "Gana local" else "Gana local"
    m = re.match(r"Hándicap (local|visitante) ([+-][\d.]+)", mercado)
    if m:
        otro = "visitante" if m.group(1) == "local" else "local"
        return f"Hándicap {otro} {-float(m.group(2)):+g}"
    m = re.match(r"(Más|Menos) de ([\d.]+) puntos", mercado)
    if m:
        return f"{'Menos' if m.group(1) == 'Más' else 'Más'} de {m.group(2)} puntos"
    return None


def poner_cuotas(j: Juego, hoy: date):
    try:
        import cuotas
        ev = cuotas.instancia(hoy).buscar(j.comp, j.fecha, j.local, j.visitante)
    except Exception as e:
        print(f"  aviso cuotas: {e}")
        return
    if ev:
        j.cuotas, j.casa = ev.cuotas, ev.casa
        if ev.spread_local is not None:
            j.spread_local = ev.spread_local
        if ev.total is not None:
            j.total_casa = ev.total


def analizar_juego(j: Juego, modelo: ModeloBaloncesto, hoy: date | None = None) -> Analisis | None:
    if not (modelo.conoce(j.local_id) and modelo.conoce(j.visit_id)):
        return None
    if hoy is not None:
        poner_cuotas(j, hoy)
    pl, pv = modelo.esperado(j)
    margen, total = pl - pv, pl + pv
    w = config.PESO_MERCADO
    if j.spread_local is not None:  # mezcla con la línea de la casa
        margen = (1 - w) * margen + w * (-j.spread_local)
    if j.total_casa is not None:
        total = (1 - w) * total + w * j.total_casa
    pl, pv = (total + margen) / 2, (total - margen) / 2
    tipico = 2 * modelo.media.get(j.comp, np.mean(list(modelo.media.values())))
    picks = mercados_baloncesto(margen, total, modelo.sd_margen, modelo.sd_total, j.spread_local,
                                j.total_casa, tipico)
    if j.cuotas:  # cuotas reales de la casa en las líneas que ofrece
        por_nombre = {pk.mercado: pk for pk in picks}
        for nombre, cuota in j.cuotas.items():
            pk = por_nombre.get(nombre)
            if not pk:
                continue
            pk.cuota, pk.estimada = cuota, False
            otro = j.cuotas.get(_contrario(nombre) or "")
            pk.prob_cuota = (1 / cuota) / (1 / cuota + 1 / otro) if otro else None
    # Cuotas estimadas (≈) para las demás líneas, a partir de la línea de la casa
    if j.spread_local is not None or j.total_casa is not None:
        from analisis import estimar_cuotas
        m_mkt = -j.spread_local if j.spread_local is not None else margen
        t_mkt = j.total_casa if j.total_casa is not None else total
        mkt = {pk.mercado: pk.prob for pk in mercados_baloncesto(m_mkt, t_mkt, modelo.sd_margen, modelo.sd_total,
                                                                 None, None, tipico)}
        if j.spread_local is None:
            mkt = {k: v for k, v in mkt.items() if "puntos" in k}
        if j.total_casa is None:
            mkt = {k: v for k, v in mkt.items() if "puntos" not in k}
        mg = 0.045
        if j.cuotas:
            pares = [(k, v) for k, v in j.cuotas.items() if _contrario(k) in j.cuotas]
            if pares:
                mg = sum(1 / v + 1 / j.cuotas[_contrario(k)] - 1 for k, v in pares) / len(pares)
        estimar_cuotas(picks, mkt, mg)
    p = PartidoProximo(j.comp, j.fecha, j.hora, j.local, j.visitante,
                       casa=j.casa or ("ESPN (línea)" if j.spread_local is not None else ""))
    return Analisis(p, pl, pv, f"{round(pl)}-{round(pv)}", 0.0, picks)


# --------------------------------------------------------------- todo junto
def analizar_dias(hoy: date, n_dias: int) -> dict[date, list[Analisis]]:
    salida: dict[date, list[Analisis]] = {}

    def procesar(nombre, juegos):
        import historial
        for j in juegos:
            if j.jugado:
                historial.anotar(j.fecha, j.local, j.visitante, j.pl, j.pv)
        proximos = [j for j in juegos if not j.jugado and hoy <= j.fecha < hoy + timedelta(days=n_dias)]
        print(f"  {nombre}: {len(juegos)} partidos, {len(proximos)} próximos")
        if not proximos:
            return
        modelo = ModeloBaloncesto().ajustar(juegos, hasta=hoy)
        for j in proximos:
            a = analizar_juego(j, modelo, hoy)
            if a:
                salida.setdefault(j.fecha, []).append(a)
            else:
                print(f"    sin datos suficientes: {j.local} - {j.visitante}")

    try:
        procesar("NBA", nba_temporada_pasada(hoy) + nba_temporada_actual(hoy, n_dias))
    except Exception as e:
        print(f"  aviso: NBA no disponible: {e}")
    try:
        procesar("baloncesto europeo", europa(hoy, n_dias))
    except Exception as e:
        import traceback
        print(f"  aviso: baloncesto europeo no disponible: {e}")
        traceback.print_exc()
    return salida
