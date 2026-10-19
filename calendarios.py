"""
Calendarios que nos faltaban:
- Basket europeo: próximos partidos de toda la temporada (365Scores), para que cada equipo enseñe
  sus siguientes partidos aunque aún no tengan probabilidades.
- Esports: partidos recientes y próximos de TODOS los niveles de torneo (bo3.gg), no solo los grandes.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import datetime, timedelta

import requests

import config

TZ_NOMBRE = config.ZONA_HORARIA
CACHE = os.path.join(config.CARPETA_CACHE, "calendarios")
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
B365 = "https://webws.365scores.com"
P365 = "appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2"


def _get(url: str, horas: float, params: dict | None = None):
    os.makedirs(CACHE, exist_ok=True)
    clave = url + json.dumps(params or {}, sort_keys=True)
    import hashlib
    ruta = os.path.join(CACHE, hashlib.md5(clave.encode()).hexdigest() + ".json")
    if os.path.exists(ruta) and time.time() - os.path.getmtime(ruta) < horas * 3600:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    try:
        r = requests.get(url, params=params, headers=UA, timeout=30)
        r.raise_for_status()
        datos = r.json()
    except (requests.RequestException, ValueError):
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
        return {}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return datos


# ------------------------------------------------------------------ basket (365Scores)
def _mejor(nombre: str, opciones: list[str]) -> tuple[str | None, float]:
    from directo import parecido
    mejor, pm = None, 0.0
    for o in opciones:
        s = parecido(nombre, o)
        if s > pm:
            mejor, pm = o, s
    return mejor, pm


def _competicion(clave: str, equipos: list[str]) -> int | None:
    """Id de la competición en 365Scores, buscando a sus equipos (se guarda para siempre)."""
    ruta = os.path.join(CACHE, "competiciones365.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            mapa = json.load(f)
    except (OSError, ValueError):
        mapa = {}
    if clave in mapa:
        return mapa[clave]
    votos: Counter = Counter()
    for eq in equipos[:4]:
        j = _get(f"{B365}/web/search/?{P365}", 24 * 30, {"query": eq, "filter": "all"})
        cands = [c for c in (j.get("competitors") or []) if c.get("sportId") == 2]
        if not cands:
            continue
        nombre, puntos = _mejor(eq, [c["name"] for c in cands])
        if puntos < 0.75:
            continue
        cid = next(c["id"] for c in cands if c["name"] == nombre)
        g = _get(f"{B365}/web/games/fixtures/?{P365}", 12, {"competitors": cid})
        for juego in g.get("games") or []:
            rival = [(juego.get(k) or {}).get("name", "") for k in ("homeCompetitor", "awayCompetitor")]
            if all(_mejor(r, equipos)[1] >= 0.75 for r in rival):
                votos[juego.get("competitionId")] += 1
    comp = votos.most_common(1)[0][0] if votos else None
    if comp:
        mapa[clave] = comp
        os.makedirs(CACHE, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(mapa, f)
    return comp


def proximos_basket(clave: str, equipos: list[str], dias: int = 45) -> list[dict]:
    """Próximos partidos de una competición de basket, con los nombres de NUESTROS equipos."""
    if len(equipos) < 4:
        return []
    cid = _competicion(clave, equipos)
    if not cid:
        return []
    limite = datetime.now().astimezone() + timedelta(days=dias)
    out, vistos = [], set()
    url, params = f"{B365}/web/games/fixtures/?{P365}", {"competitions": cid}
    for _ in range(20):
        j = _get(url, 6, params)
        juegos = j.get("games") or []
        if not juegos:
            break
        pasado_limite = False
        for g in juegos:
            if g.get("id") in vistos or g.get("statusGroup") not in (1, 2):  # 1-2 = por jugar
                continue
            vistos.add(g.get("id"))
            try:
                dt = datetime.fromisoformat(g["startTime"])
            except (KeyError, ValueError):
                continue
            if dt > limite:
                pasado_limite = True
                continue
            l = (g.get("homeCompetitor") or {}).get("name", "")
            v = (g.get("awayCompetitor") or {}).get("name", "")
            ml, pl = _mejor(l, equipos)
            mv, pv = _mejor(v, equipos)
            from zoneinfo import ZoneInfo
            loc = dt.astimezone(ZoneInfo(TZ_NOMBRE))
            out.append({"f": loc.date().isoformat(), "h": loc.strftime("%H:%M"),
                        "l": ml if pl >= 0.75 else l, "v": mv if pv >= 0.75 else v})
        sig = (j.get("paging") or {}).get("nextPage")
        if pasado_limite or not sig:
            break
        url, params = B365 + sig, None
    return out


# ------------------------------------------------------------------ esports (bo3.gg, todos los niveles)
def esports_extra(juego: str, disc: int, dias: int = 30) -> list:
    """Series terminadas en los últimos `dias` y próximas en los siguientes `dias`, de cualquier nivel."""
    import esports
    hoy = datetime.now().astimezone()
    out = []
    for estado, orden, paginas in (("finished", "-start_date", 5), ("upcoming", "start_date", 4), ("current", "start_date", 1)):
        for pag in range(paginas):
            j = _get(esports.URL, 1, {"page[offset]": pag * 100, "page[limit]": 100, "sort": orden,
                                      "filter[matches.status][in]": estado, "filter[matches.discipline_id][eq]": disc,
                                      "with": "teams,tournament"})
            res = j.get("results") or []
            fuera = False
            for m in res:
                s = esports._a_serie(juego, m)
                if not s:
                    continue
                dif = (s.fecha - hoy.date()).days
                if abs(dif) > dias:
                    # Los "próximos" viejos que nunca se actualizaron no cortan la búsqueda: solo lo muy lejano
                    if (estado == "finished" and dif < 0) or (estado != "finished" and dif > 0):
                        fuera = True
                    continue
                out.append(s)
            if fuera or len(res) < 100:
                break
    return out


# ------------------------------------------------------------------ copas de fútbol (365Scores)
# ESPN tarda en meter los cruces de una ronda recién sorteada; 365Scores los tiene en cuanto se sortean.
ALIAS_COPA = {
    "copadelrey": ["copa del rey"], "supercopa": ["supercopa de espana", "supercopa"], "facup": ["fa cup"],
    "carabao": ["carabao", "efl cup", "league cup"], "coppa": ["coppa italia"], "pokal": ["dfb pokal", "pokal"],
    "coupe": ["coupe de france"], "knvb": ["knvb", "beker"], "taca": ["taca de portugal"],
    "copaarg": ["copa argentina"], "copabrasil": ["copa do brasil", "copa de brasil"],
    "libertadores": ["libertadores"], "sudamericana": ["sudamericana"],
    "champions": ["champions league"], "europa": ["europa league"], "conference": ["conference league"],
}


def _norm(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return " ".join(t.replace("-", " ").split())


def _competicion_copa(clave: str, equipos: list[str]) -> int | None:
    ruta = os.path.join(CACHE, "copas365.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            mapa = json.load(f)
    except (OSError, ValueError):
        mapa = {}
    if mapa.get(clave):
        return mapa[clave]
    alias = ALIAS_COPA.get(clave) or []
    for eq in equipos[:8]:
        j = _get(f"{B365}/web/search/?{P365}", 24 * 30, {"query": eq, "filter": "all"})
        cands = [c for c in (j.get("competitors") or []) if c.get("sportId") == 1]
        if not cands:
            continue
        nombre, puntos = _mejor(eq, [c["name"] for c in cands])
        if puntos < 0.75:
            continue
        cid = next(c["id"] for c in cands if c["name"] == nombre)
        for url in (f"{B365}/web/games/fixtures/?{P365}", f"{B365}/web/games/results/?{P365}"):
            g = _get(url, 12, {"competitors": cid})
            for juego in g.get("games") or []:
                n = _norm(juego.get("competitionDisplayName") or "")
                if any(a in n for a in alias):
                    mapa[clave] = juego.get("competitionId")
                    os.makedirs(CACHE, exist_ok=True)
                    with open(ruta, "w", encoding="utf-8") as f:
                        json.dump(mapa, f)
                    return mapa[clave]
    return None


def _logo365(cid) -> str:
    return f"https://imagecache.365scores.com/image/upload/f_png,w_68,h_68,c_limit,q_auto:eco,d_Competitors:default1.png/Competitors/{cid}" if cid else ""


def proximos_copa(clave: str, partidos: list[dict], dias: int = 120) -> list[dict]:
    """Cruces ya sorteados que aún no están en `partidos` (los de ESPN), con la ronda."""
    from directo import parecido
    from zoneinfo import ZoneInfo
    cuenta = Counter(n for p in partidos for n in (p["l"], p["v"]) if n and n != "Por decidir")
    equipos = [n for n, _ in cuenta.most_common()]
    if not equipos:
        return []
    cid = _competicion_copa(clave, equipos)
    if not cid:
        return []
    logos = {}
    for p in partidos:
        logos.setdefault(p["l"], p.get("el") or "")
        logos.setdefault(p["v"], p.get("ev") or "")
    limite = datetime.now().astimezone() + timedelta(days=dias)
    out, vistos = [], set()
    url, params = f"{B365}/web/games/fixtures/?{P365}", {"competitions": cid}
    for _ in range(15):
        j = _get(url, 4, params)
        juegos = j.get("games") or []
        if not juegos:
            break
        fuera = False
        for g in juegos:
            if g.get("id") in vistos or g.get("statusGroup") not in (1, 2):
                continue
            vistos.add(g.get("id"))
            try:
                dt = datetime.fromisoformat(g["startTime"]).astimezone(ZoneInfo(TZ_NOMBRE))
            except (KeyError, ValueError):
                continue
            if dt > limite:
                fuera = True
                continue
            h, a = g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}
            l, v = h.get("name", ""), a.get("name", "")
            f = dt.date().isoformat()
            # ¿Ya lo trae ESPN? (mismo día, más o menos, y algún equipo parecido)
            ya = any(abs((datetime.fromisoformat(p["f"]) - datetime.fromisoformat(f)).days) <= 1
                     and (parecido(p["l"], l) >= 0.75 or parecido(p["v"], v) >= 0.75) for p in partidos)
            if ya:
                continue
            ml, pl = _mejor(l, equipos)
            mv, pv = _mejor(v, equipos)
            ronda = (g.get("competitionDisplayName") or "").split(" - ", 1)
            nl, nv = (ml if pl >= 0.85 else l), (mv if pv >= 0.85 else v)
            out.append({"f": f, "h": dt.strftime("%H:%M"), "l": nl, "v": nv,
                        "el": logos.get(nl) or _logo365(h.get("id")), "ev": logos.get(nv) or _logo365(a.get("id")), "m": "", "st": "pre",
                        "r": ronda[1].strip().capitalize() if len(ronda) > 1 else "", "fuente": "365"})
        sig = (j.get("paging") or {}).get("nextPage")
        if fuera or not sig:
            break
        url, params = B365 + sig, None
    return out
