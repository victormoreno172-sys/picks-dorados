"""
Ficha de cada partido (pantalla de detalle de la app): escudos, estadio, alineaciones,
clasificación y últimos partidos de cada equipo. Todo sale de ESPN (gratis, sin clave).

Se empareja cada partido de la app con el de ESPN por liga, fecha, hora y nombres.
"""
from __future__ import annotations

import difflib
import json
import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config

TZ = ZoneInfo(config.ZONA_HORARIA)
CACHE = os.path.join(config.CARPETA_CACHE, "fichas")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://site.api.espn.com/apis/site/v2/sports/{deporte}/{slug}/{que}"

# Nombre de la liga en la app -> (deporte, liga en ESPN)
SLUGS = {
    "LaLiga": ("soccer", "esp.1"), "Segunda División": ("soccer", "esp.2"), "Premier League": ("soccer", "eng.1"),
    "Championship": ("soccer", "eng.2"), "Serie A": ("soccer", "ita.1"), "Bundesliga": ("soccer", "ger.1"),
    "Ligue 1": ("soccer", "fra.1"), "Eredivisie": ("soccer", "ned.1"), "Liga Portugal": ("soccer", "por.1"),
    "MLS": ("soccer", "usa.1"), "Liga Argentina": ("soccer", "arg.1"),
    "Champions League": ("soccer", "uefa.champions"), "Europa League": ("soccer", "uefa.europa"),
    "Conference League": ("soccer", "uefa.europa.conf"),
    "NBA": ("basketball", "nba"), "NBA · Pretemporada": ("basketball", "nba"),
}
DIAS_CON_DETALLE = 3  # alineaciones, clasificación y forma solo para los próximos días


def _get(deporte: str, slug: str, que: str, params: dict, horas: float, base: str = BASE) -> dict:
    os.makedirs(CACHE, exist_ok=True)
    nombre = ("v2_" if base != BASE else "") + f"{deporte}_{slug}_{que}_" + "_".join(f"{k}{v}" for k, v in sorted(params.items())) + ".json"
    ruta = os.path.join(CACHE, nombre.replace("/", "-"))
    if os.path.exists(ruta) and time.time() - os.path.getmtime(ruta) < horas * 3600:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    try:
        r = requests.get(base.format(deporte=deporte, slug=slug, que=que), params=params, headers=UA, timeout=30)
        r.raise_for_status()
        datos = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  aviso fichas {slug} {que}: {e}")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
        return {}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return datos


def _norm(t: str) -> str:
    import europa
    return europa.normalizar(t)


def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


def _eventos(deporte: str, slug: str, dia: date) -> list[dict]:
    out = []
    hoy = datetime.now(TZ).date()
    horas = 0.15 if abs((dia - hoy).days) <= 1 else 3  # hoy: marcadores frescos
    for e in (_get(deporte, slug, "scoreboard", {"dates": f"{dia:%Y%m%d}"}, horas).get("events") or []):
        try:
            c = e["competitions"][0]
            eq = {t["homeAway"]: t for t in c["competitors"]}
            dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(TZ)
            v = c.get("venue") or {}
            out.append({"id": e["id"], "fecha": dt.date(), "hora": dt.strftime("%H:%M"),
                        "local": eq["home"]["team"]["displayName"], "visitante": eq["away"]["team"]["displayName"],
                        "esc": [eq["home"]["team"].get("logo", ""), eq["away"]["team"].get("logo", "")],
                        "estadio": ", ".join(x for x in (v.get("fullName"), (v.get("address") or {}).get("city")) if x),
                        "estado": _estado(c, eq)})
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    return out


def _estado(c: dict, eq: dict) -> dict | None:
    """Marcador y estado de ESPN: None si no ha empezado."""
    t = ((c.get("status") or {}).get("type") or {})
    st = t.get("state")
    if st not in ("in", "post"):
        return None
    if t.get("name") in ("STATUS_POSTPONED", "STATUS_CANCELED"):
        return {"st": "susp", "m": "", "det": "Aplazado"}
    try:
        m = f"{int(eq['home']['score'])}-{int(eq['away']['score'])}"
    except (KeyError, ValueError, TypeError):
        m = ""
    det = "Final" if st == "post" else ((c.get("status") or {}).get("displayClock") or t.get("shortDetail") or "En juego")
    return {"st": st, "m": m, "det": det}


def _emparejar(p: dict, fecha: date, eventos: list[dict]) -> dict | None:
    mejor, puntos = None, 0.0
    for e in eventos:
        if abs((e["fecha"] - fecha).days) > 1:
            continue
        s = _sim(p["local"], e["local"]) + _sim(p["visitante"], e["visitante"])
        if p.get("hora") and e["hora"] == p["hora"]:
            s += 0.4  # misma hora de inicio: casi seguro que es ese
        if s > puntos:
            mejor, puntos = e, s
    return mejor if puntos >= 1.2 else None


def _alineaciones(s: dict) -> dict | None:
    out = {}
    for r in s.get("rosters") or []:
        jug = r.get("roster") or []
        if not jug:
            continue
        lado = "l" if r.get("homeAway") == "home" else "v"
        tit = [j for j in jug if j.get("starter")]
        sup = [j for j in jug if not j.get("starter")]
        fila = lambda j: [j.get("jersey") or "", (j.get("athlete") or {}).get("displayName") or "?",
                          ((j.get("position") or {}).get("abbreviation") or "")]
        out[lado] = {"form": r.get("formation") or "", "tit": [fila(j) for j in tit], "sup": [fila(j) for j in sup][:12]}
    return out or None


def _forma(s: dict) -> dict | None:
    out = {}
    for i, t in enumerate(s.get("lastFiveGames") or []):
        lado = "l" if i == 0 else "v"
        partidos = []
        for e in (t.get("events") or [])[:5]:
            partidos.append({"r": e.get("gameResult", ""), "m": e.get("score", ""), "a": e.get("atVs", ""),
                             "o": (e.get("opponent") or {}).get("displayName", ""), "f": (e.get("gameDate") or "")[:10]})
        out[lado] = sorted(partidos, key=lambda e: e["f"], reverse=True)  # el más reciente primero
    return out or None


def _tabla(s: dict) -> list | None:
    try:
        grupos = s["standings"]["groups"]
    except (KeyError, TypeError):
        return None
    filas = []
    for g in grupos:
        for e in (g.get("standings") or {}).get("entries") or []:
            st = {x.get("name"): x.get("displayValue") for x in e.get("stats") or []}
            nombre = e.get("team") if isinstance(e.get("team"), str) else (e.get("team") or {}).get("displayName", "")
            filas.append([st.get("rank", ""), nombre, st.get("gamesPlayed", ""), st.get("wins", ""), st.get("ties", ""),
                          st.get("losses", ""), st.get("pointDifferential", ""), st.get("points", "")])
        if len(grupos) > 1:
            filas.append(None)  # separador entre grupos
    return [f for f in filas if f is not None] if filas else None


def enriquecer(datos_app: dict):
    """Añade a cada partido de la app su ficha (campo "fi") y las clasificaciones (datos_app["tablas"])."""
    hoy = datetime.now(TZ).date()
    tablas, n_fichas, n_detalle = {}, 0, 0
    cache_ev: dict[tuple, list] = {}
    for dia in datos_app.get("dias", []):
        fecha = date.fromisoformat(dia["fecha"])
        for p in dia["partidos"]:
            ds = SLUGS.get(p.get("liga"))
            if not ds:
                continue
            evs = []
            for d in (fecha - timedelta(days=1), fecha, fecha + timedelta(days=1)):
                clave = (*ds, d)
                if clave not in cache_ev:
                    cache_ev[clave] = _eventos(*ds, d)
                evs += cache_ev[clave]
            e = _emparejar(p, fecha, evs)
            if not e:
                continue
            fi = {"id": e["id"], "slug": ds[1], "esc": e["esc"], "estadio": e["estadio"], "n": [e["local"], e["visitante"]]}
            if e.get("estado"):
                p["res"] = e["estado"]
            if (fecha - hoy).days < DIAS_CON_DETALLE:
                horas = 0.5 if fecha == hoy else 3
                s = _get(*ds, "summary", {"event": e["id"]}, horas)
                if s:
                    al, fo, tb = _alineaciones(s), _forma(s), _tabla(s)
                    if al:
                        fi["alin"] = al
                    if fo:
                        fi["forma"] = fo
                    if tb and ds[1] not in tablas:
                        tablas[ds[1]] = tb
                    n_detalle += 1
            p["fi"] = fi
            n_fichas += 1
    _otros_deportes(datos_app, tablas)
    datos_app["tablas"] = tablas
    print(f"  fichas: {n_fichas} partidos con escudos y estadio, {n_detalle} con detalle, {len(tablas)} clasificaciones")


# ---------------------------------------------------- basket europeo, tenis y esports
def _forma_de(nombre: str, partidos: list, campos, sin_local: bool = False) -> list:
    """Últimos 5 de un equipo/jugador (tanteo desde su punto de vista).
    campos(p) -> (fecha, local, visitante, tanteo_l, tanteo_v)."""
    out, vistos = [], set()
    for p in partidos:
        f, l, v, a, b = campos(p)
        if nombre not in (l, v) or a is None or (f, l, v) in vistos:
            continue
        vistos.add((f, l, v))
        mio, suyo = (a, b) if nombre == l else (b, a)
        out.append({"r": "W" if mio > suyo else "L" if mio < suyo else "D", "m": f"{mio}-{suyo}",
                    "a": "vs" if sin_local or nombre == l else "@", "o": v if nombre == l else l, "f": f.isoformat()})
    return sorted(out, key=lambda e: e["f"], reverse=True)[:5]


def _tabla_basket(comp: str, jugados: list, hoy: date) -> list | None:
    inicio = date(hoy.year if hoy.month >= 8 else hoy.year - 1, 8, 1)
    st: dict[str, list] = {}
    for j in jugados:
        if j.comp != comp or j.fecha < inicio:
            continue
        for eq, a, b in ((j.local, j.pl, j.pv), (j.visitante, j.pv, j.pl)):
            r = st.setdefault(eq, [0, 0, 0])
            r[0 if a > b else 1] += 1
            r[2] += a - b
    if len(st) < 4:
        return None
    orden = sorted(st.items(), key=lambda kv: (-kv[1][0] / max(1, kv[1][0] + kv[1][1]), -kv[1][2]))
    return [[str(i), eq, str(r[0] + r[1]), str(r[0]), "0", str(r[1]), f"{r[2]:+d}", str(r[0])]
            for i, (eq, r) in enumerate(orden, 1)]


def _otros_deportes(datos_app: dict, tablas: dict):
    hoy = datetime.now(TZ).date()
    import baloncesto, esports, tenis
    codigo = {config.nombre_liga(c).split(" ", 1)[-1]: c for c in config.BASKET}
    n = 0
    for dia in datos_app.get("dias", []):
        for p in dia["partidos"]:
            if p.get("dep") not in ("b", "te", "e"):
                continue
            r = _resultado_propio(p, dia["fecha"])
            if r:
                p["res"] = r
            if p.get("fi"):
                continue
            clave = (dia["fecha"], p["local"], p["visitante"])
            fi = {"n": [p["local"], p["visitante"]]}
            if p["dep"] == "b":
                fi.update(baloncesto.INFO.get(clave, {}))
                campos = lambda j: (j.fecha, j.local, j.visitante, j.pl, j.pv)
                fi["forma"] = {"l": _forma_de(p["local"], baloncesto.JUGADOS, campos),
                               "v": _forma_de(p["visitante"], baloncesto.JUGADOS, campos)}
                c = codigo.get(p["liga"])
                if c and c != "NBA":
                    clave_t = "b-" + c
                    if clave_t not in tablas:
                        t = _tabla_basket(c, baloncesto.JUGADOS, hoy)
                        if t:
                            tablas[clave_t] = t
                    if clave_t in tablas:
                        fi["slug"] = clave_t
            elif p["dep"] == "te":
                fi.update(tenis.INFO.get(clave, {}))
                campos = lambda h: (h.fecha, h.n1, h.n2, h.s1, h.s2)
                fi["forma"] = {"l": _forma_de(p["local"], tenis.HIST, campos, True),
                               "v": _forma_de(p["visitante"], tenis.HIST, campos, True)}
            else:
                fi.update(esports.INFO.get(clave, {}))
                campos = lambda s: (s.fecha, s.n1, s.n2, s.m1, s.m2)
                fi["forma"] = {"l": _forma_de(p["local"], esports.HIST, campos, True),
                               "v": _forma_de(p["visitante"], esports.HIST, campos, True)}
            if not (fi["forma"]["l"] or fi["forma"]["v"]):
                fi.pop("forma")
            p["fi"] = fi
            n += 1
    print(f"  fichas de basket europeo, tenis y esports: {n}")


def _resultado_propio(p: dict, fecha: str) -> dict | None:
    """Resultado de basket europeo, tenis y esports con nuestros propios datos."""
    import baloncesto, esports, tenis
    if p["dep"] == "b":
        for j in baloncesto.JUGADOS:
            if j.fecha.isoformat() == fecha and j.local == p["local"] and j.visitante == p["visitante"]:
                return {"st": "post", "m": f"{j.pl}-{j.pv}", "det": "Final"}
    elif p["dep"] == "te":
        for h in tenis.HIST:
            if h.fecha.isoformat() == fecha and {h.n1, h.n2} == {p["local"], p["visitante"]}:
                a, b = (h.s1, h.s2) if h.n1 == p["local"] else (h.s2, h.s1)
                return {"st": "post", "m": f"{a}-{b}", "det": "Ret." if h.retirada else "Final"}
    elif p["dep"] == "e":
        for x in esports.HIST:
            if x.fecha.isoformat() == fecha and {x.n1, x.n2} == {p["local"], p["visitante"]}:
                a, b = (x.m1, x.m2) if x.n1 == p["local"] else (x.m2, x.m1)
                return {"st": "post", "m": f"{a}-{b}", "det": "Final"}
    return None


def recuperar_empezados(datos_app: dict, ruta_previa: str):
    """Los partidos de hoy que ya han empezado desaparecen de los cálculos (ya no hay cuotas antes
    del partido). Se recuperan de la versión anterior de la app, con sus probabilidades, para
    poder enseñarlos con el resultado."""
    try:
        with open(ruta_previa, encoding="utf-8") as f:
            previo = json.load(f)
    except (OSError, ValueError):
        return
    hoy = datetime.now(TZ).date().isoformat()
    ayer = (datetime.now(TZ).date() - timedelta(days=1)).isoformat()
    previos = {d["fecha"]: d for d in previo.get("dias", [])}
    n = 0
    for dia in datos_app.get("dias", []):
        if dia["fecha"] not in (hoy, ayer) or dia["fecha"] not in previos:
            continue
        ya = {(p["liga"], p["local"], p["visitante"]) for p in dia["partidos"]}
        for p in previos[dia["fecha"]]["partidos"]:
            if (p["liga"], p["local"], p["visitante"]) not in ya:
                p.pop("res", None)
                dia["partidos"].append(p)
                n += 1
        dia["partidos"].sort(key=lambda p: (p.get("hora") or "99", p["liga"]))
    print(f"  partidos ya empezados recuperados de la versión anterior: {n}")
