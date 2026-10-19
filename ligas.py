"""
Pestaña "Ligas" de la app Partidos: clasificación con zonas (Champions, Europa, descenso...),
todas las jornadas de la temporada con resultados y los equipos de cada competición.

Fútbol y NBA salen de ESPN (gratis, sin clave). El basket europeo, de nuestros propios datos.
Se escribe un índice (web/ligas/indice.json) y un archivo por liga que el móvil carga al abrirla.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta

import config
import ficha

SALIDA = os.path.join("web", "ligas")
STANDINGS = "https://site.api.espn.com/apis/v2/sports/{deporte}/{slug}/{que}"

# id del archivo -> (nombre en la app, deporte ESPN, slug ESPN)
LIGAS = [
    ("laliga", "LaLiga", "soccer", "esp.1"), ("segunda", "Segunda División", "soccer", "esp.2"),
    ("premier", "Premier League", "soccer", "eng.1"), ("championship", "Championship", "soccer", "eng.2"),
    ("seriea", "Serie A", "soccer", "ita.1"), ("bundesliga", "Bundesliga", "soccer", "ger.1"),
    ("ligue1", "Ligue 1", "soccer", "fra.1"), ("eredivisie", "Eredivisie", "soccer", "ned.1"),
    ("portugal", "Liga Portugal", "soccer", "por.1"), ("mls", "MLS", "soccer", "usa.1"),
    ("argentina", "Liga Argentina", "soccer", "arg.1"), ("brasil", "Brasileirão", "soccer", "bra.1"),
    ("champions", "Champions League", "soccer", "uefa.champions"), ("europa", "Europa League", "soccer", "uefa.europa"),
    ("conference", "Conference League", "soccer", "uefa.europa.conf"),
    ("nba", "NBA", "basketball", "nba"),
]
# Copas y torneos sin clasificación (solo calendario por rondas)
COPAS = [
    ("copadelrey", "Copa del Rey", "esp.copa_del_rey"), ("supercopa", "Supercopa de España", "esp.super_cup"),
    ("facup", "FA Cup", "eng.fa"), ("carabao", "Copa de la Liga inglesa", "eng.league_cup"),
    ("coppa", "Coppa Italia", "ita.coppa_italia"), ("pokal", "DFB-Pokal", "ger.dfb_pokal"),
    ("coupe", "Coupe de France", "fra.coupe_de_france"), ("knvb", "Copa de Holanda", "ned.cup"),
    ("taca", "Taça de Portugal", "por.taca.portugal"), ("copaarg", "Copa Argentina", "arg.copa"), ("copabrasil", "Copa do Brasil", "bra.copa_do_brazil"),
    ("libertadores", "Copa Libertadores", "conmebol.libertadores"),
    ("sudamericana", "Copa Sudamericana", "conmebol.sudamericana"),
]
AÑO_NATURAL = {"usa.1", "arg.1", "bra.1", "bra.copa_do_brazil", "arg.copa", "conmebol.libertadores", "conmebol.sudamericana"}
RONDAS = [("round of 128", "Ronda de 128"), ("round of 64", "Treintaidosavos"), ("round of 32", "Dieciseisavos"),
          ("round of 16", "Octavos de final"), ("quarterfinal", "Cuartos de final"), ("quarter-final", "Cuartos de final"),
          ("semifinal", "Semifinales"), ("semi-final", "Semifinales"), ("final", "Final"),
          ("first round", "Primera ronda"), ("second round", "Segunda ronda"), ("third round", "Tercera ronda"),
          ("fourth round", "Cuarta ronda"), ("fifth round", "Quinta ronda"), ("preliminary", "Ronda previa"),
          ("qualifying", "Previa"), ("group", "Fase de grupos"), ("knockout", "Playoff")]


def _ronda(t: str) -> str:
    b = (t or "").lower()
    for k, v in RONDAS:
        if k in b:
            ida = " (ida)" if "1st leg" in b or "first leg" in b else " (vuelta)" if "2nd leg" in b or "second leg" in b else ""
            return v + ida
    return ""  # temporadas de enero a diciembre

# Zonas propias para el basket (ESPN no las da para Europa)
ZONAS_BASKET = {
    "EL": [(1, 6, "#16a34a", "Playoffs"), (7, 10, "#2563eb", "Play-in")],
    "EC": [(1, 8, "#16a34a", "Eliminatorias")],
    "ACB": [(1, 8, "#16a34a", "Playoffs"), (-2, -1, "#e11d48", "Descenso")],
    "LBA": [(1, 8, "#16a34a", "Playoffs"), (-1, -1, "#e11d48", "Descenso")],
    "LNB": [(1, 8, "#16a34a", "Playoffs")], "BBL": [(1, 6, "#16a34a", "Playoffs"), (7, 10, "#2563eb", "Play-in")],
    "BSL": [(1, 8, "#16a34a", "Playoffs")], "GBL": [(1, 8, "#16a34a", "Playoffs")],
    "ABA": [(1, 4, "#16a34a", "Playoffs")], "LKL": [(1, 8, "#16a34a", "Playoffs")],
}
# Ligas de fútbol a las que ESPN no les pone zonas
ZONAS_FUTBOL = {"bra.1": [(1, 4, "#16a34a", "Copa Libertadores"), (5, 6, "#86efac", "Previa de Libertadores"),
                          (7, 12, "#2563eb", "Copa Sudamericana"), (-4, -1, "#e11d48", "Descenso")]}
ZONAS_NBA = [(1, 6, "#16a34a", "Playoffs"), (7, 10, "#2563eb", "Play-in")]

TRADUCCION = [  # (texto de ESPN en minúsculas contiene..., texto en español). El orden importa.
    ("relegation play", "Promoción de descenso"), ("relegation", "Descenso"),
    ("promotion play", "Playoff de ascenso"), ("promotion", "Ascenso"),
    ("champions league qual", "Previa de Champions"), ("champions league", "Champions League"),
    ("europa league qual", "Previa de Europa League"), ("europa league", "Europa League"),
    ("conference league qual", "Previa de Conference"), ("conference league", "Conference League"),
    ("round of 16", "Octavos de final"), ("knockout", "Playoff de eliminatorias"),
    ("libertadores", "Copa Libertadores"), ("sudamericana", "Copa Sudamericana"),
    ("play-in", "Play-in"), ("wild card", "Play-in"), ("playoff", "Playoffs"), ("eliminated", "Eliminado"),
]


def _traducir(t: str) -> str:
    b = (t or "").lower()
    for k, v in TRADUCCION:
        if k in b:
            return v
    return t or ""


def _num(x, defecto=0):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return defecto


# ---------------------------------------------------------------- clasificación
def _clasif_espn(deporte: str, slug: str) -> list[dict]:
    datos = {}
    if deporte == "basketball":  # temporada regular, no la pretemporada
        datos = ficha._get(deporte, slug, "standings", {"seasontype": 2}, 2, base=STANDINGS)
    if not (datos.get("children") or datos.get("standings")):
        datos = ficha._get(deporte, slug, "standings", {}, 2, base=STANDINGS)
    hijos = datos.get("children") or ([datos] if datos.get("standings") else [])
    grupos = []
    for h in hijos:
        filas = []
        for e in (h.get("standings") or {}).get("entries") or []:
            t = e.get("team") or {}
            st = {x.get("name"): x for x in e.get("stats") or []}
            v = lambda n, d="": (st.get(n) or {}).get("displayValue", d)
            n = lambda n: _num((st.get(n) or {}).get("value"))
            nota = e.get("note") or {}
            logo = ((t.get("logos") or [{}])[0]).get("href", "")
            if deporte == "soccer":
                fila = {"eq": t.get("displayName", ""), "logo": logo, "pj": n("gamesPlayed"), "g": n("wins"),
                        "e": n("ties"), "p": n("losses"), "gf": n("pointsFor"), "gc": n("pointsAgainst"),
                        "dg": n("pointDifferential"), "pts": n("points"), "pos": n("rank")}
            else:
                fila = {"eq": t.get("displayName", ""), "logo": logo, "g": n("wins"), "p": n("losses"),
                        "pj": n("wins") + n("losses"), "pct": v("winPercent"), "gb": v("gamesBehind", "-"),
                        "racha": v("streak"), "pos": n("playoffSeed") or 0}
            if nota.get("description"):
                fila["zona"] = ["#" + (nota.get("color") or "94a3b8").lstrip("#"), _traducir(nota["description"])]
            filas.append(fila)
        if not filas:
            continue
        if deporte == "soccer":
            filas.sort(key=lambda f: (f["pos"] or 999, -f["pts"], -f["dg"]))
            if slug in ZONAS_FUTBOL and not any("zona" in f for f in filas):
                _poner_zonas(filas, ZONAS_FUTBOL[slug])
        else:
            filas.sort(key=lambda f: (-(f["g"] / max(1, f["pj"])), f["p"]))
            _poner_zonas(filas, ZONAS_NBA, sobrescribir=False)
        for i, f in enumerate(filas, 1):
            f["pos"] = f.get("pos") if deporte == "soccer" and f.get("pos") else i
        nombre = h.get("name") or h.get("abbreviation") or ""
        grupos.append({"n": _nombre_grupo(nombre) if len(hijos) > 1 else "", "filas": filas})
    return grupos


def _nombre_grupo(n: str) -> str:
    return (n.replace("Eastern Conference", "Conferencia Este").replace("Western Conference", "Conferencia Oeste")
            .replace("Group", "Grupo").replace("Zone", "Zona"))


def _poner_zonas(filas: list, zonas: list, sobrescribir: bool = True):
    total = len(filas)
    for desde, hasta, color, texto in zonas:
        a = desde if desde > 0 else total + desde + 1
        b = hasta if hasta > 0 else total + hasta + 1
        for f in filas[a - 1:b]:
            if sobrescribir or "zona" not in f:
                f["zona"] = [color, texto]


# ---------------------------------------------------------------- calendario
def _temporada(slug: str, hoy: date) -> tuple[date, date]:
    if slug in AÑO_NATURAL:
        return date(hoy.year, 1, 1), date(hoy.year, 12, 31)
    a = hoy.year if hoy.month >= 7 else hoy.year - 1
    inicio = date(a, 10, 1) if slug == "nba" else date(a, 8, 1)
    return inicio, date(a + 1, 6, 30)


def _scoreboard_rango(deporte: str, slug: str, desde: date, hasta: date, horas: float) -> dict:
    """Partidos de un mes (ESPN acepta dates=AAAAMM; los rangos de días dan error 400)."""
    datos = ficha._get(deporte, slug, "scoreboard", {"dates": f"{desde:%Y%m}", "limit": 500}, horas)
    if not datos.get("events"):
        datos = ficha._get(deporte, slug, "scoreboard", {"dates": f"{desde:%Y%m}"}, horas)
    return datos


def _calendario_espn(deporte: str, slug: str, hoy: date) -> list[dict]:
    inicio, fin = _temporada(slug, hoy)
    partidos, vistos = [], set()
    m = date(inicio.year, inicio.month, 1)
    while m <= fin:
        sig = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        ultimo = sig - timedelta(days=1)
        horas = 24 * 20 if ultimo < hoy - timedelta(days=3) else 2 if m <= hoy else 12
        datos = _scoreboard_rango(deporte, slug, m, ultimo, horas)
        for e in datos.get("events") or []:
            if e.get("id") in vistos:
                continue
            if slug == "nba" and ((e.get("season") or {}).get("type") or 2) == 1:
                continue  # pretemporada fuera
            try:
                c = e["competitions"][0]
                eq = {t["homeAway"]: t for t in c["competitors"]}
                dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(ficha.TZ)
            except (KeyError, IndexError, ValueError, TypeError):
                continue
            vistos.add(e.get("id"))
            es = ficha._estado(c, eq) or {}
            notas = c.get("notes") or e.get("notes") or []
            for lado in ("home", "away"):
                if re.match(r"^TBD", eq[lado]["team"].get("displayName", "") or ""):
                    eq[lado]["team"]["displayName"], eq[lado]["team"]["logo"] = "Por decidir", ""
            partidos.append({"il": eq["home"]["team"].get("id", ""), "iv": eq["away"]["team"].get("id", ""),
                             "r": _ronda((notas[0] or {}).get("headline", "") if notas else ""),"f": dt.date().isoformat(), "h": dt.strftime("%H:%M"),
                             "l": eq["home"]["team"].get("displayName", ""), "v": eq["away"]["team"].get("displayName", ""),
                             "el": eq["home"]["team"].get("logo", ""), "ev": eq["away"]["team"].get("logo", ""),
                             "m": es.get("m", ""), "st": es.get("st", "pre"),
                             "fase": (e.get("season") or {}).get("slug", "")})
            if _eliminatoria(e, slug):
                partidos[-1]["ko"] = 1
        m = sig
    partidos.sort(key=lambda p: (p["f"], p["h"]))
    return partidos


def _eliminatoria(e: dict, slug: str) -> bool:
    """¿Partido de eliminatorias (playoffs de la NBA, rondas K.O. de copas y competiciones europeas)?"""
    se = e.get("season") or {}
    if slug == "nba":
        return se.get("type") == 3
    f = (se.get("slug") or "").lower()
    if re.search(r"group|league|regular|qualif|pre-?season|swiss", f):
        return False
    return bool(re.search(r"post|playoff|knockout|round-of|quarter|semi|final|eighth|16|ko", f))


def _jornadas_liga(partidos: list) -> list[dict]:
    """Liga a doble vuelta: la jornada de un partido es el nº de partido que juega cada equipo
    (el mayor de los dos). Así un aplazado no descuadra el resto de jornadas."""
    cuenta: dict[str, int] = {}
    por_j: dict[int, list] = {}
    for p in partidos:  # ya vienen ordenados por fecha
        a, b = cuenta.get(p["l"], 0) + 1, cuenta.get(p["v"], 0) + 1
        cuenta[p["l"]], cuenta[p["v"]] = a, b
        por_j.setdefault(max(a, b), []).append(p)
    out = []
    for n in sorted(por_j):
        b = sorted(por_j[n], key=lambda p: (p["f"], p["h"]))
        for p in b:
            p.pop("fase", None)
        fechas = sorted(p["f"] for p in b)
        # el rango de fechas sin contar aplazados sueltos muy alejados
        medio = fechas[len(fechas) // 2]
        cerca = [f for f in fechas if abs((date.fromisoformat(f) - date.fromisoformat(medio)).days) <= 4] or fechas
        out.append({"t": f"Jornada {n}", "desde": cerca[0], "hasta": cerca[-1], "p": b})
    return out


def _rondas_copa(partidos: list) -> list[dict]:
    """Copas: bloques de fechas seguidas; el título es la ronda si ESPN la dice."""
    bloques: list[list] = []
    for p in partidos:
        d = date.fromisoformat(p["f"])
        if bloques and (d - date.fromisoformat(bloques[-1][-1]["f"])).days <= 3 \
                and (not p.get("r") or p["r"] == bloques[-1][-1].get("r")):
            bloques[-1].append(p)
        else:
            bloques.append([p])
    out = []
    for i, b in enumerate(bloques, 1):
        rondas = [p.get("r") for p in b if p.get("r")]
        titulo = max(set(rondas), key=rondas.count) if rondas else f"Ronda {i}"
        if any(x["t"] == titulo for x in out):
            titulo += f" · {_dia_corto(b[0]['f'])}"
        out.append({"t": titulo, "desde": b[0]["f"], "hasta": b[-1]["f"], "p": b})
    return out


def _jornadas(partidos: list, n_equipos: int, por_dia: bool = False, uefa: bool = False) -> list[dict]:
    """Agrupa los partidos en jornadas por fechas (los de una jornada se juegan en 1-4 días seguidos)."""
    if not partidos:
        return []
    if not por_dia and not uefa:
        return _jornadas_liga(partidos)
    bloques: list[list] = []
    for p in partidos:
        d = date.fromisoformat(p["f"])
        if bloques:
            b = bloques[-1]
            ini, ult = date.fromisoformat(b[0]["f"]), date.fromisoformat(b[-1]["f"])
            mismo = d == ult if por_dia else ((d - ini).days <= 3 and (d - ult).days <= 2)
            if mismo:
                b.append(p)
                continue
        bloques.append([p])
    if not por_dia and not uefa and n_equipos >= 4:
        # Partidos sueltos (aplazados) se pegan a la jornada anterior
        minimo = max(2, n_equipos // 4)
        juntos = []
        for b in bloques:
            if juntos and len(b) < minimo:
                juntos[-1].extend(b)
            else:
                juntos.append(b)
        bloques = juntos
    out = []
    for i, b in enumerate(bloques, 1):
        for p in b:
            p.pop("fase", None)
        titulo = f"{_dia_corto(b[0]['f'])}" if por_dia else f"Jornada {i}"
        out.append({"t": titulo, "desde": b[0]["f"], "hasta": b[-1]["f"], "p": b})
    return out


DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _dia_corto(f: str) -> str:
    d = date.fromisoformat(f)
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"


def _actual(jornadas: list, hoy: date) -> int:
    for i, j in enumerate(jornadas):
        if j["hasta"] >= hoy.isoformat() or sum(p["st"] != "post" for p in j["p"]) > len(j["p"]) // 2:
            return i
    return max(0, len(jornadas) - 1)


# ---------------------------------------------------------------- basket europeo
def _basket_europa(datos_app: dict, hoy: date) -> list[tuple[str, dict]]:
    try:
        import baloncesto
    except ImportError:
        return []
    out = []
    for c, (nombre, _) in config.BASKET_EUROPA.items():
        nombre = nombre.split(" ", 1)[-1]
        inicio = date(hoy.year if hoy.month >= 8 else hoy.year - 1, 8, 1)
        logos: dict[str, str] = {}
        for (f, l, v), inf in baloncesto.INFO.items():
            for eq, url in zip((l, v), inf.get("esc") or []):
                if url:
                    logos.setdefault(eq, url)
        partidos, vistos = [], set()
        for j in baloncesto.JUGADOS:
            if j.comp == c and j.fecha >= inicio and (j.fecha, j.local, j.visitante) not in vistos:
                vistos.add((j.fecha, j.local, j.visitante))
                partidos.append({"f": j.fecha.isoformat(), "h": j.hora or "", "l": j.local, "v": j.visitante,
                                 "el": logos.get(j.local, ""), "ev": logos.get(j.visitante, ""),
                                 "m": f"{j.pl}-{j.pv}", "st": "post"})
        for dia in datos_app.get("dias", []):
            for p in dia["partidos"]:
                if p.get("dep") == "b" and p.get("liga") == nombre:
                    k = (date.fromisoformat(dia["fecha"]), p["local"], p["visitante"])
                    if k in vistos:
                        continue
                    vistos.add(k)
                    r = p.get("res") or {}
                    partidos.append({"f": dia["fecha"], "h": p.get("hora") or "", "l": p["local"], "v": p["visitante"],
                                     "el": logos.get(p["local"], ""), "ev": logos.get(p["visitante"], ""),
                                     "m": r.get("m", ""), "st": r.get("st", "pre")})
        # Próximos partidos de toda la temporada (365Scores), aunque aún no tengan probabilidades
        try:
            import calendarios
            equipos = sorted({p["l"] for p in partidos} | {p["v"] for p in partidos})
            ya = {(p["f"], p["l"], p["v"]) for p in partidos} | {(p["f"], p["v"], p["l"]) for p in partidos}
            for q in calendarios.proximos_basket(c, equipos):
                if (q["f"], q["l"], q["v"]) in ya or q["f"] < hoy.isoformat() or q["l"] not in equipos or q["v"] not in equipos:
                    continue
                ya.add((q["f"], q["l"], q["v"]))
                partidos.append({"f": q["f"], "h": q["h"], "l": q["l"], "v": q["v"], "el": logos.get(q["l"], ""),
                                 "ev": logos.get(q["v"], ""), "m": "", "st": "pre"})
        except Exception as e:  # noqa: BLE001
            print(f"  aviso calendario 365 {c}: {e}")
        if len(partidos) < 4:
            continue
        partidos.sort(key=lambda p: (p["f"], p["h"]))
        # Playoffs: en la fase regular cada pareja se ve como mucho dos veces (ida y vuelta);
        # a partir del tercer cruce entre los mismos equipos es eliminatoria (serie, play-in o Final Four)
        veces: dict[frozenset, int] = {}
        for p in partidos:
            k = frozenset((p["l"], p["v"]))
            veces[k] = veces.get(k, 0) + 1
            if veces[k] >= 3:
                p["ko"] = 1
        st: dict[str, list] = {}
        for p in partidos:
            if p["st"] != "post" or "-" not in p["m"] or p.get("ko"):  # la clasificación, solo con la fase regular
                continue
            a, b = map(int, p["m"].split("-"))
            for eq, x, y in ((p["l"], a, b), (p["v"], b, a)):
                r = st.setdefault(eq, [0, 0, 0, 0])
                r[0 if x > y else 1] += 1
                r[2] += x
                r[3] += y
        for p in partidos:
            for eq in (p["l"], p["v"]):
                st.setdefault(eq, [0, 0, 0, 0])
        filas = [{"eq": eq, "logo": logos.get(eq, ""), "g": r[0], "p": r[1], "pj": r[0] + r[1],
                  "pf": r[2], "pc": r[3], "dif": r[2] - r[3]} for eq, r in st.items()]
        filas.sort(key=lambda f: (-(f["g"] / max(1, f["pj"])), -f["g"], -f["dif"]))
        for i, f in enumerate(filas, 1):
            f["pos"] = i
        _poner_zonas(filas, ZONAS_BASKET.get(c, []))
        jor = _jornadas(partidos, len(filas))
        out.append((f"b-{c.lower()}", {"nombre": nombre, "dep": "b", "tipo": "basket",
                                        "grupos": [{"n": "", "filas": filas}], "jornadas": jor,
                                        "actual": _actual(jor, hoy)}))
    return out




# ---------------------------------------------------------------- tenis y esports
def _slug(t: str) -> str:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def _tenis(hoy: date, nombres_app: set | None = None) -> list[tuple[str, dict]]:
    try:
        import tenis
    except ImportError:
        return []
    out = []
    banderas: dict[str, str] = {}
    for p in list(tenis.HIST) + list(tenis.PROX):
        if p.flag1:
            banderas.setdefault(p.n1, p.flag1)
        if p.flag2:
            banderas.setdefault(p.n2, p.flag2)
    for tour, elo in tenis.ELO.items():
        hist = [h for h in tenis.HIST if h.tour == tour]
        nombre = {}
        for h in hist:
            nombre[h.j1], nombre[h.j2] = h.n1, h.n2
        hace_un_año = hoy - timedelta(days=365)
        rec: dict[str, list] = {}
        for h in hist:
            if h.fecha < hace_un_año or h.gana1 is None:
                continue
            for j, gano in ((h.j1, h.gana1), (h.j2, not h.gana1)):
                r = rec.setdefault(j, [0, 0])
                r[0 if gano else 1] += 1
        candidatos = [j for j in rec if sum(rec[j]) >= 8]
        candidatos.sort(key=lambda j: -elo.general.get(j, 1500))
        filas = [{"pos": i, "eq": nombre.get(j, j), "logo": banderas.get(nombre.get(j, j), ""), "pj": sum(rec[j]),
                  "g": rec[j][0], "p": rec[j][1], "nivel": round(elo.general.get(j, 1500))}
                 for i, j in enumerate(candidatos[:100], 1)]
        if not filas:
            continue
        # Últimos partidos de cada jugador del ranking (para su ficha)
        top = {f["eq"] for f in filas} | (nombres_app or set())
        otras: dict[str, list] = {}
        for h in sorted(hist, key=lambda h: h.fecha, reverse=True):
            for n in (h.n1, h.n2):
                if n in top and len(otras.setdefault(n, [])) < 15:
                    otras[n].append({"f": h.fecha.isoformat(), "h": h.hora or "", "l": h.n1, "v": h.n2,
                                     "el": banderas.get(h.n1, ""), "ev": banderas.get(h.n2, ""),
                                     "m": f"{h.s1}-{h.s2}" if h.s1 is not None else "", "st": "post", "c": h.torneo})
        for p in tenis.PROX:
            if p.tour != tour:
                continue
            for n in (p.n1, p.n2):
                if n in top:
                    otras.setdefault(n, []).append({"f": p.fecha.isoformat(), "h": p.hora or "", "l": p.n1, "v": p.n2,
                                                    "el": banderas.get(p.n1, ""), "ev": banderas.get(p.n2, ""),
                                                    "m": "", "st": "pre", "c": p.torneo})
        out.append((f"t-{tour.lower()}-ranking", {"nombre": f"{tour} · Ranking por nivel", "dep": "te", "tipo": "ranking",
                    "grupos": [{"n": "", "filas": filas}], "jornadas": [], "actual": 0, "otras": otras,
                    "nota": "Ranking según el nivel que calcula la app (Elo) con los partidos del último año; "
                            "no es el ranking oficial."}))
        # Torneos en juego: los que tienen partidos en los últimos 10 días o en los próximos
        torneos: dict[str, list] = {}
        for h in hist:
            if h.fecha >= hoy - timedelta(days=10):
                torneos.setdefault(h.torneo, []).append(h)
        for p in tenis.PROX:
            if p.tour == tour:
                torneos.setdefault(p.torneo, []).append(p)
        for torneo, ps in torneos.items():
            if not any(x.fecha >= hoy - timedelta(days=2) for x in ps) or len(ps) < 4:
                continue
            vistos, partidos = set(), []
            for x in sorted(ps, key=lambda x: (x.fecha, x.hora or "")):
                k = (x.fecha, x.n1, x.n2)
                if k in vistos:
                    continue
                vistos.add(k)
                jugado = x.gana1 is not None
                partidos.append({"f": x.fecha.isoformat(), "h": x.hora or "", "l": x.n1, "v": x.n2,
                                 "el": banderas.get(x.n1, ""), "ev": banderas.get(x.n2, ""),
                                 "m": f"{x.s1}-{x.s2}" if jugado and x.s1 is not None else "",
                                 "st": "post" if jugado else "pre", "r": _ronda(x.ronda) or x.ronda or ""})
            # Rondas en el orden en que se juegan
            rondas: dict[str, list] = {}
            for q in partidos:
                rondas.setdefault(q.pop("r") or "Partidos", []).append(q)
            jor = [{"t": r, "desde": min(q["f"] for q in l), "hasta": max(q["f"] for q in l), "p": l}
                   for r, l in sorted(rondas.items(), key=lambda kv: min(q["f"] for q in kv[1]))]
            out.append((f"t-{tour.lower()}-{_slug(torneo)}", {"nombre": f"{tour} · {torneo}", "dep": "te", "tipo": "copa",
                        "grupos": [], "jornadas": jor, "actual": _actual(jor, hoy)}))
    return out


def _esports(hoy: date, nombres_app: set | None = None) -> list[tuple[str, dict]]:
    try:
        import esports
    except ImportError:
        return []
    # Además de los torneos grandes, partidos recientes y próximos de todos los niveles
    try:
        import calendarios
        vistos = {s.id for s in list(esports.HIST) + list(esports.PROX)}
        for juego, (_, disc, _) in esports.JUEGOS.items():
            for s in calendarios.esports_extra(juego, disc):
                if s.id in vistos:
                    continue
                vistos.add(s.id)
                (esports.HIST if s.m1 is not None else esports.PROX).append(s)
    except Exception as e:  # noqa: BLE001
        print(f"  aviso esports extra: {e}")
    nombres_app = nombres_app or set()
    out = []
    logos: dict[str, str] = {}
    for s in list(esports.HIST) + list(esports.PROX):
        if s.img1:
            logos.setdefault(s.n1, s.img1)
        if s.img2:
            logos.setdefault(s.n2, s.img2)
    juegos = sorted({s.juego for s in esports.HIST} | set(esports.MODELOS))
    for juego in juegos:
        hist = [s for s in esports.HIST if s.juego == juego and (s.m1 or s.m2)]
        modelo = esports.MODELOS.get(juego)
        nombre = {}
        for s in hist:
            nombre[s.eq1], nombre[s.eq2] = s.n1, s.n2
        if modelo is not None:
            rec: dict[str, list] = {}
            for s in hist:
                if s.fecha < hoy - timedelta(days=120):
                    continue
                for e, gano in ((s.eq1, s.m1 > s.m2), (s.eq2, s.m2 > s.m1)):
                    r = rec.setdefault(e, [0, 0])
                    r[0 if gano else 1] += 1
            eqs = [e for e in rec if sum(rec[e]) >= 4 and e in modelo.fuerza]
            eqs.sort(key=lambda e: -modelo.fuerza[e])
            filas = [{"pos": i, "eq": nombre.get(e, e), "logo": logos.get(nombre.get(e, e), ""), "pj": sum(rec[e]),
                      "g": rec[e][0], "p": rec[e][1], "nivel": round(1500 + 200 * modelo.fuerza[e])}
                     for i, e in enumerate(eqs[:60], 1)]
            top = {f["eq"] for f in filas} | nombres_app  # también los equipos que salen en la app
            otras: dict[str, list] = {}
            for s in sorted(hist, key=lambda s: s.fecha, reverse=True):
                for n in (s.n1, s.n2):
                    if n in top and len(otras.setdefault(n, [])) < 15:
                        otras[n].append({"f": s.fecha.isoformat(), "h": s.hora or "", "l": s.n1, "v": s.n2,
                                         "el": logos.get(s.n1, ""), "ev": logos.get(s.n2, ""),
                                         "m": f"{s.m1}-{s.m2}", "st": "post", "c": s.torneo})
            for s in esports.PROX:
                if s.juego == juego:
                    for n in (s.n1, s.n2):
                        if n in top:
                            otras.setdefault(n, []).append({"f": s.fecha.isoformat(), "h": s.hora or "", "l": s.n1,
                                                            "v": s.n2, "el": logos.get(s.n1, ""), "ev": logos.get(s.n2, ""),
                                                            "m": "", "st": "pre", "c": s.torneo})
            if filas:
                out.append((f"e-{juego.lower()}-ranking", {"nombre": f"{juego} · Ranking de equipos", "dep": "e",
                            "tipo": "ranking", "grupos": [{"n": "", "filas": filas}], "jornadas": [], "actual": 0,
                            "otras": otras, "nota": "Ranking según la fuerza que calcula la app con los mapas de los "
                                                    "últimos meses (torneos de nivel S y A); no es un ranking oficial."}))
        # Torneos en juego
        torneos: dict[str, list] = {}
        for s in esports.HIST:
            if s.juego == juego and s.fecha >= hoy - timedelta(days=21) and (s.nivel or "").lower() in ("s", "a"):
                torneos.setdefault(s.torneo, []).append(s)
        for s in esports.PROX:
            if s.juego == juego and (s.nivel or "").lower() in ("s", "a"):
                torneos.setdefault(s.torneo, []).append(s)
        for torneo, ss in torneos.items():
            # Torneo terminado hace más de 2 días: fuera (la edición del año siguiente saldrá como nueva)
            if not torneo.strip() or not any(x.fecha >= hoy - timedelta(days=2) for x in ss) or len(ss) < 3:
                continue
            vistos, partidos = set(), []
            st: dict[str, list] = {}
            for x in sorted(ss, key=lambda x: (x.fecha, x.hora or "")):
                k = (x.fecha, x.n1, x.n2)
                if k in vistos:
                    continue
                vistos.add(k)
                jugado = bool(x.m1 or x.m2)
                partidos.append({"f": x.fecha.isoformat(), "h": x.hora or "", "l": x.n1, "v": x.n2,
                                 "el": logos.get(x.n1, ""), "ev": logos.get(x.n2, ""),
                                 "m": f"{x.m1}-{x.m2}" if jugado else "", "st": "post" if jugado else "pre"})
                for n in (x.n1, x.n2):
                    st.setdefault(n, [0, 0, 0])
                if jugado:
                    for n, a, b in ((x.n1, x.m1, x.m2), (x.n2, x.m2, x.m1)):
                        st[n][0 if a > b else 1] += 1
                        st[n][2] += a - b
            filas = [{"eq": n, "logo": logos.get(n, ""), "g": r[0], "p": r[1], "pj": r[0] + r[1], "dif": r[2]}
                     for n, r in st.items()]
            filas.sort(key=lambda f: (-f["g"], f["p"], -f["dif"]))
            for i, f in enumerate(filas, 1):
                f["pos"] = i
            jor = _jornadas(partidos, len(filas), por_dia=True)
            grupos_t = [{"n": "", "filas": filas}]
            # Con las fases del torneo (bo3.gg): Fase 1 · Grupo A, Fase 2 · Playoffs (Semifinales, Final...)
            try:
                import fases
                slug = next((x.slug for x in ss if x.slug), "") or fases.slug_de(torneo)
                E = fases.estructura(slug, torneo)
                if E:
                    jor_f, grupos_f = _jornadas_fases(E, logos)
                    if jor_f:
                        jor = jor_f
                        if grupos_f:
                            grupos_t = grupos_f
            except Exception as e:  # noqa: BLE001
                print(f"  aviso fases {torneo}: {e}")
            out.append((f"e-{juego.lower()}-{_slug(torneo)}", {"nombre": f"{juego} · {torneo}", "dep": "e", "tipo": "basket",
                        "grupos": grupos_t, "jornadas": jor, "actual": _actual(jor, hoy)}))
    return out

def _jornadas_fases(E: dict, logos: dict) -> tuple[list, list]:
    """Una "jornada" por fase (y por grupo), con la ronda de cada partido; y la tabla de cada grupo."""
    import fases
    bloques: dict[tuple, list] = {}
    tablas: dict[tuple, dict] = {}
    tipos: dict[tuple, str] = {}
    for f, grupo, ronda, orden, m in fases.partidos(E):
        t1, t2 = m.get("team1") or {}, m.get("team2") or {}
        n1, n2 = t1.get("name") or "Por decidir", t2.get("name") or "Por decidir"
        fe, h = fases.fecha_hora(m.get("start_date") or "")
        if not fe:
            continue
        for t in (t1, t2):
            if t.get("name") and t.get("image_url"):
                logos.setdefault(t["name"], t["image_url"])
        hecho = m.get("status") == "finished"
        vivo = m.get("status") == "current"
        a, b = m.get("team1_score"), m.get("team2_score")
        p = {"f": fe, "h": h, "l": n1, "v": n2, "el": logos.get(n1, t1.get("image_url") or ""), "ev": logos.get(n2, t2.get("image_url") or ""),
             "m": f"{a}-{b}" if (hecho or vivo) and a is not None and b is not None else "", "st": "post" if hecho else "in" if vivo else "pre",
             "r": ronda, "ro": orden, "pos": m.get("position") or 0, "_o": (orden, fe, h)}
        clave = (f["n"], f["nombre"] + (f" · {grupo}" if grupo else ""))
        bloques.setdefault(clave, []).append(p)
        tipos[clave] = f["tipo"]
        # Tabla de los grupos (y de la fase suiza)
        if f["tipo"] == "grupo" and hecho and t1.get("name") and t2.get("name"):
            tb = tablas.setdefault(clave, {})
            for n, x, y in ((n1, a or 0, b or 0), (n2, b or 0, a or 0)):
                r = tb.setdefault(n, [0, 0, 0])
                r[0 if x > y else 1] += 1
                r[2] += x - y
        elif f["tipo"] == "grupo":
            tb = tablas.setdefault(clave, {})
            for n in (n1, n2):
                if n != "Por decidir":
                    tb.setdefault(n, [0, 0, 0])
    jor = []
    for (n, titulo), ps in sorted(bloques.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        ps.sort(key=lambda p: p.pop("_o"))
        jor.append({"t": titulo, "desde": min(p["f"] for p in ps), "hasta": max(p["f"] for p in ps), "p": ps,
                    "tipo": tipos.get((n, titulo), "")})
    grupos = []
    for (n, titulo), tb in sorted(tablas.items()):
        filas = [{"eq": e, "logo": logos.get(e, ""), "g": r[0], "p": r[1], "pj": r[0] + r[1], "dif": r[2]} for e, r in tb.items()]
        filas.sort(key=lambda f: (-f["g"], f["p"], -f["dif"]))
        for i, f in enumerate(filas, 1):
            f["pos"] = i
        grupos.append({"n": titulo, "filas": filas})
    return jor, grupos


# ---------------------------------------------------------------- escudos que faltan
PAIS_DE = {"copadelrey": "Spain", "supercopa": "Spain", "segunda": "Spain", "laliga": "Spain", "facup": "England",
           "carabao": "England", "championship": "England", "coppa": "Italy", "pokal": "Germany", "coupe": "France",
           "knvb": "Netherlands", "taca": "Portugal", "copaarg": "Argentina", "copabrasil": "Brazil", "brasil": "Brazil",
           "argentina": "Argentina", "mls": "USA"}


def _completar_escudos(archivos: list):
    """Primero con los escudos que ya salen en otras competiciones; luego, TheSportsDB."""
    try:
        import escudos
    except ImportError:
        return
    conocidos: dict[str, str] = {}
    for _, d in archivos:
        for j in d["jornadas"]:
            for p in j["p"]:
                for n, u in ((p["l"], p.get("el")), (p["v"], p.get("ev"))):
                    if u:
                        conocidos.setdefault(n, u)
        for g in d["grupos"]:
            for f in g["filas"]:
                if f.get("logo"):
                    conocidos.setdefault(f["eq"], f["logo"])
    n_nuevos = 0
    for lid, d in archivos:
        if d.get("dep") != "f":
            continue
        pais = PAIS_DE.get(lid, "")
        def logo(n):
            nonlocal n_nuevos
            if n in conocidos or n == "Por decidir":
                return conocidos.get(n, "")
            u = escudos.escudo(n, pais)
            if u:
                conocidos[n] = u
                n_nuevos += 1
            return u
        for j in d["jornadas"]:
            for p in j["p"]:
                if not p.get("el"):
                    p["el"] = logo(p["l"])
                if not p.get("ev"):
                    p["ev"] = logo(p["v"])
        for g in d["grupos"]:
            for f in g["filas"]:
                if not f.get("logo"):
                    f["logo"] = logo(f["eq"])
        for lista in (d.get("otras") or {}).values():
            for p in lista:
                p["el"] = p.get("el") or conocidos.get(p["l"], "")
                p["ev"] = p.get("ev") or conocidos.get(p["v"], "")
    escudos.guardar()
    print(f"  escudos: {n_nuevos} encontrados en TheSportsDB")


# ---------------------------------------------------------------- todo junto
def _leyenda(grupos: list) -> list:
    vistas, out = set(), []
    for g in grupos:
        for f in g["filas"]:
            z = f.get("zona")
            if z and z[1] not in vistas:
                vistas.add(z[1])
                out.append(z)
    return out


def _equipos(grupos: list, jornadas: list) -> list:
    eqs: dict[str, str] = {}
    for g in grupos:
        for f in g["filas"]:
            eqs.setdefault(f["eq"], f.get("logo", ""))
    if not eqs:  # sin clasificación (p. ej. aún no ha empezado): los del calendario
        for j in jornadas:
            for p in j["p"]:
                eqs.setdefault(p["l"], p["el"])
                eqs.setdefault(p["v"], p["ev"])
    return sorted(([n, l] for n, l in eqs.items()), key=lambda x: x[0])


def escribir(datos_app: dict, carpeta: str = SALIDA):
    hoy = datetime.now(ficha.TZ).date()
    os.makedirs(carpeta, exist_ok=True)
    indice = []
    archivos: list[tuple[str, dict]] = []
    for lid, nombre, deporte, slug in LIGAS:
        try:
            grupos = _clasif_espn(deporte, slug)
            cal = _calendario_espn(deporte, slug, hoy)
        except Exception as e:  # una liga rota no tumba las demás
            print(f"  aviso ligas {nombre}: {e}")
            continue
        n_eq = sum(len(g["filas"]) for g in grupos) or len({p["l"] for p in cal} | {p["v"] for p in cal})
        jor = _jornadas(cal, n_eq, por_dia=deporte == "basketball", uefa=slug.startswith("uefa"))
        if not grupos and not jor:
            continue
        archivos.append((lid, {"nombre": nombre, "dep": "f" if deporte == "soccer" else "b",
                               "tipo": "futbol" if deporte == "soccer" else "nba", "grupos": grupos,
                               "jornadas": jor, "actual": _actual(jor, hoy)}))
    todos: list[tuple[str, dict]] = [(d["nombre"], p) for _, d in archivos if d["tipo"] == "futbol"
                                     for j in d["jornadas"] for p in j["p"]]
    for lid, nombre, slug in COPAS:
        try:
            cal = _calendario_espn("soccer", slug, hoy)
        except Exception as e:  # noqa: BLE001
            print(f"  aviso copas {nombre}: {e}")
            continue
        if not cal:
            continue
        jor = _rondas_copa(cal)
        archivos.append((lid, {"nombre": nombre, "dep": "f", "tipo": "copa", "grupos": [], "jornadas": jor,
                               "actual": _actual(jor, hoy)}))
        todos += [(nombre, p) for p in cal]
    # Cada equipo con TODOS sus partidos: liga, copas y competiciones europeas
    por_id: dict[str, list] = {}
    for comp, p in todos:
        for k in (p.get("il"), p.get("iv")):
            if k:
                por_id.setdefault(k, []).append((comp, p))
    for _, d in archivos:
        if d["dep"] != "f":
            continue
        ids: dict[str, str] = {}
        for j in d["jornadas"]:
            for p in j["p"]:
                ids.setdefault(p["l"], p.get("il", ""))
                ids.setdefault(p["v"], p.get("iv", ""))
        otras = {}
        for eq, i in ids.items():
            ext = [dict(p, c=comp) for comp, p in por_id.get(i, []) if comp != d["nombre"]]
            if ext:
                otras[eq] = sorted(ext, key=lambda p: (p["f"], p["h"]))
        d["otras"] = otras
    for _, d in archivos:  # fuera lo que el móvil no necesita
        for lista in [p for j in d["jornadas"] for p in j["p"]] + [p for o in d.get("otras", {}).values() for p in o]:
            if lista.get("r") and d.get("tipo") == "copa":
                lista["rn"] = lista["r"]  # nombre de la ronda (si ESPN lo da) para el cuadro
            for k in ("il", "iv", "r", "fase"):
                lista.pop(k, None)
    archivos += _basket_europa(datos_app, hoy)
    nombres_e = {n for d in datos_app.get("dias", []) for p in d["partidos"] if p.get("dep") == "e" for n in (p["local"], p["visitante"])}
    nombres_t = {n for d in datos_app.get("dias", []) for p in d["partidos"] if p.get("dep") == "te" for n in (p["local"], p["visitante"])}
    for extra in (lambda h: _tenis(h, nombres_t), lambda h: _esports(h, nombres_e)):
        try:
            archivos += extra(hoy)
        except Exception as e:  # noqa: BLE001
            import traceback
            print(f"  aviso ligas tenis/esports: {e}")
            traceback.print_exc()
    _completar_escudos(archivos)
    for lid, d in archivos:
        d["leyenda"] = _leyenda(d["grupos"])
        d["equipos"] = _equipos(d["grupos"], d["jornadas"])
        d["generado"] = datetime.now(ficha.TZ).strftime("%d/%m %H:%M")
        with open(os.path.join(carpeta, f"{lid}.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
        indice.append({"id": lid, "n": d["nombre"], "dep": d["dep"], "tipo": d["tipo"], "eq": len(d["equipos"]),
                       "j": len(d["jornadas"])})
    # Índice para el buscador general: todos los equipos y jugadores de todas las competiciones
    buscar: dict[str, list] = {}
    JUEGO = {"e-cs2": "Counter-Strike 2", "e-val": "Valorant", "e-lol": "League of Legends"}
    FEM = re.compile(r"game changers|female|women|femenin|\blgc\b|girls|ladies|equal esports|\bgc\b|frost", re.I)
    torneos_de: dict[str, set] = {}   # torneos de cada equipo de esports (para saber si es femenino)
    for lid, d in archivos:
        if d["dep"] != "e":
            continue
        for j in d["jornadas"]:
            for p in j["p"]:
                for n in (p["l"], p["v"]):
                    torneos_de.setdefault(f"{lid[:5]}|{n}", set()).add(d["nombre"])
        for n, ps in (d.get("otras") or {}).items():
            torneos_de.setdefault(f"{lid[:5]}|{n}", set()).update(p.get("c", "") for p in ps)

    def detalle(lid: str, d: dict, n: str) -> str:
        if d["dep"] == "e":
            fem = any(FEM.search(t or "") for t in torneos_de.get(f"{lid[:5]}|{n}", ()))
            return JUEGO.get(lid[:5], "Esports") + (" · Femenino" if fem else "")
        if d["dep"] == "te":
            return "ATP · masculino" if lid.startswith("t-atp") else "WTA · femenino" if lid.startswith("t-wta") else "Tenis"
        return d["nombre"]
    for lid, d in archivos:
        nombres = {n: l for n, l in d.get("equipos", [])}
        for n in (d.get("otras") or {}):
            nombres.setdefault(n, "")
        for n, logo in nombres.items():
            if not n or n == "Por decidir":
                continue
            # Preferimos la liga/ranking (donde está su ficha completa) antes que copas y torneos sueltos
            peso = 0 if d["tipo"] in ("futbol", "nba", "basket", "ranking") else 1
            k = f'{d["dep"]}|{lid[:5] if d["dep"] == "e" else ""}|{n}'  # mismo nombre en dos juegos = dos equipos
            if k not in buscar or peso < buscar[k][4]:
                buscar[k] = [n, logo or (buscar.get(k) or ["", ""])[1], lid, d["dep"], peso, detalle(lid, d, n)]
    with open(os.path.join(carpeta, "buscar.json"), "w", encoding="utf-8") as f:
        json.dump([v[:4] + [v[5]] for v in buscar.values()], f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(carpeta, "indice.json"), "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False)
    print(f"  ligas: {len(indice)} competiciones con clasificación y calendario")
