"""
Pestaña "Ligas" de la app Partidos: clasificación con zonas (Champions, Europa, descenso...),
todas las jornadas de la temporada con resultados y los equipos de cada competición.

Fútbol y NBA salen de ESPN (gratis, sin clave). El basket europeo, de nuestros propios datos.
Se escribe un índice (web/ligas/indice.json) y un archivo por liga que el móvil carga al abrirla.
"""
from __future__ import annotations

import json
import os
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
            partidos.append({"il": eq["home"]["team"].get("id", ""), "iv": eq["away"]["team"].get("id", ""),
                             "r": _ronda((notas[0] or {}).get("headline", "") if notas else ""),"f": dt.date().isoformat(), "h": dt.strftime("%H:%M"),
                             "l": eq["home"]["team"].get("displayName", ""), "v": eq["away"]["team"].get("displayName", ""),
                             "el": eq["home"]["team"].get("logo", ""), "ev": eq["away"]["team"].get("logo", ""),
                             "m": es.get("m", ""), "st": es.get("st", "pre"),
                             "fase": (e.get("season") or {}).get("slug", "")})
        m = sig
    partidos.sort(key=lambda p: (p["f"], p["h"]))
    return partidos


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
        if len(partidos) < 4:
            continue
        partidos.sort(key=lambda p: (p["f"], p["h"]))
        st: dict[str, list] = {}
        for p in partidos:
            if p["st"] != "post" or "-" not in p["m"]:
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
            for k in ("il", "iv", "r", "fase"):
                lista.pop(k, None)
    archivos += _basket_europa(datos_app, hoy)
    for lid, d in archivos:
        d["leyenda"] = _leyenda(d["grupos"])
        d["equipos"] = _equipos(d["grupos"], d["jornadas"])
        d["generado"] = datetime.now(ficha.TZ).strftime("%d/%m %H:%M")
        with open(os.path.join(carpeta, f"{lid}.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
        indice.append({"id": lid, "n": d["nombre"], "dep": d["dep"], "tipo": d["tipo"], "eq": len(d["equipos"]),
                       "j": len(d["jornadas"])})
    with open(os.path.join(carpeta, "indice.json"), "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False)
    print(f"  ligas: {len(indice)} competiciones con clasificación y calendario")
