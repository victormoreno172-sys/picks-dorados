"""
Servidor de directo: durante ~58 minutos, cada minuto mira los marcadores de los partidos que se
están jugando (basket europeo en LiveScore, esports en bo3.gg) y los deja en directo.json en la
rama "directo". El móvil lo lee cada minuto. Lo arranca cada hora el workflow directo.yml.

LiveScore no deja leer sus datos desde una web (CORS), pero sí desde aquí.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Europe/Madrid")
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
DATOS = "https://victormoreno172-sys.github.io/picks-dorados/datos.json"
DURACION = 58 * 60
FUERA = re.compile(r"\b(bc|kk|sk|bk|fc|cb|club|basket|basketball|basketbol|basquet|pallacanestro|esports|esport|gaming|team|clan)\b")
PERIODO = {"Q1": "1C", "Q2": "2C", "Q3": "3C", "Q4": "4C", "HT": "Desc.", "OT": "Prór.", "1Q": "1C", "2Q": "2C", "3Q": "3C", "4Q": "4C"}


def nom(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", FUERA.sub(" ", t)).strip()


def parecido(a: str, b: str) -> float:
    x, y = nom(a), nom(b)
    if not x or not y:
        return 0
    if x == y:
        return 1
    if x in y or y in x:
        return 0.9
    xs, ys = x.replace(" ", ""), y.replace(" ", "")
    if len(xs) > 4 and len(ys) > 4 and (xs in ys or ys in xs):
        return 0.85
    tx, ty = {w for w in x.split() if len(w) > 2}, [w for w in y.split() if len(w) > 2]
    comun = sum(1 for w in ty if w in tx)
    if comun:
        return 0.5 + 0.4 * comun / max(len(tx), len(ty))
    return 0.6 if difflib.SequenceMatcher(None, xs, ys).ratio() > 0.8 else 0


def buscar(cand: list, casa: str, fuera: str):
    mejor, pm = None, 1.15
    for p in cand:
        d = parecido(p["local"], casa) + parecido(p["visitante"], fuera)
        r = parecido(p["local"], fuera) + parecido(p["visitante"], casa)
        if d > pm:
            mejor, pm = (p, False), d
        if r > pm:
            mejor, pm = (p, True), r
    return mejor


def candidatos(datos: dict, ahora: datetime) -> dict:
    out = {"b": [], "e": []}
    for dia in datos.get("dias", []):
        for p in dia["partidos"]:
            dep = p.get("dep", "f")
            if dep not in out or ((p.get("fi") or {}).get("slug") == "nba"):
                continue
            try:
                ini = datetime.fromisoformat(f"{dia['fecha']}T{p.get('hora') or '00:00'}").replace(tzinfo=TZ)
            except ValueError:
                continue
            # esports: las series largas (Bo5) y los retrasos alargan mucho los partidos
            if ini - timedelta(minutes=10) <= ahora <= ini + timedelta(hours=12 if dep == "e" else 5):
                out[dep].append({"clave": f"{dia['fecha']}|{p['local']}|{p['visitante']}", "local": p["local"],
                                 "visitante": p["visitante"], "liga": p.get("liga") or ""})
    return out


def basket(cand: list, ahora: datetime) -> dict:
    res = {}
    for f in {ahora.date(), (ahora - timedelta(hours=6)).date()}:
        try:
            j = requests.get(f"https://prod-public-api.livescore.com/v1/api/app/date/basketball/{f:%Y%m%d}/2?MD=1",
                             headers=UA, timeout=25).json()
        except (requests.RequestException, ValueError):
            continue
        for st in j.get("Stages") or []:
            for ev in st.get("Events") or []:
                eps = (ev.get("Eps") or "").upper()
                if eps in ("NS", "CANC", "POSTP", ""):
                    continue
                t1, t2 = (ev.get("T1") or [{}])[0].get("Nm", ""), (ev.get("T2") or [{}])[0].get("Nm", "")
                x = buscar(cand, t1, t2)
                if not x or ev.get("Tr1") in (None, "") or ev.get("Tr2") in (None, ""):
                    continue
                a, b = int(ev["Tr1"]), int(ev["Tr2"])
                # Puntos de cada cuarto (y prórroga)
                cab, p1, p2 = [], [], []
                for q, n in (("Q1", "1C"), ("Q2", "2C"), ("Q3", "3C"), ("Q4", "4C"), ("OT", "Pr")):
                    if ev.get(f"Tr1{q}") not in (None, "") and ev.get(f"Tr2{q}") not in (None, ""):
                        cab.append(n); p1.append(int(ev[f"Tr1{q}"])); p2.append(int(ev[f"Tr2{q}"]))
                if x[1]:
                    a, b, p1, p2 = b, a, p2, p1
                fin = eps in ("FT", "AOT", "AP", "AET")
                res[x[0]["clave"]] = {"st": "post" if fin else "in", "m": f"{a}-{b}",
                                      "det": "Final" if fin else PERIODO.get(eps, eps or "Vivo"),
                                      "parc": {"cab": cab, "l": p1, "v": p2}}
    return res


# ---------------------------------------------------------------- Counter-Strike ronda a ronda (DRAFT5)
# DRAFT5 (web brasileña de CS) narra muchos partidos ronda a ronda y deja leer sus datos.
D5_API = "https://api.draft5.gg/matches/"
D5_H = {**UA, "Accept": "application/json", "Origin": "https://draft5.gg", "Referer": "https://draft5.gg/"}
_D5 = {"t": 0, "links": []}


def _d5_links() -> list:
    """Partidos que salen en la portada de DRAFT5 (los de hoy y en directo): [(id, texto del enlace)]"""
    if time.time() - _D5["t"] > 600:
        try:
            t = requests.get("https://draft5.gg/", headers={**UA, "Accept": "text/html"}, timeout=25).text
            _D5["links"] = list({m.group(1): m.group(2) for m in re.finditer(r'/partida/(\d+)-([^"?#]+)', t)}.items())
            _D5["t"] = time.time()
        except requests.RequestException:
            pass
    return _D5["links"]


def draft5(local: str, visitante: str) -> dict | None:
    """Marcador de la serie, mapa a mapa y rondas del mapa en juego, desde el punto de vista del local."""
    nl, nv = nom(local).replace(" ", ""), nom(visitante).replace(" ", "")
    if not nl or not nv:
        return None
    mid = None
    for i, txt in _d5_links():
        x = nom(txt.replace("-", " ")).replace(" ", "")
        if nl in x and nv in x:
            mid = i
            break
    if not mid:
        return None
    try:
        d = requests.get(D5_API + mid, headers=D5_H, timeout=20).json().get("data") or {}
    except (requests.RequestException, ValueError):
        return None
    if not d.get("scores"):
        return None
    giro = parecido((d.get("teamA") or {}).get("teamName", ""), visitante) > parecido((d.get("teamA") or {}).get("teamName", ""), local)
    sa, sb = int(d.get("seriesScoreA") or 0), int(d.get("seriesScoreB") or 0)
    jugados = sa + sb
    scores = sorted(d["scores"], key=lambda z: z.get("seriesOrder") or 0)
    ultimo = {}
    try:  # narración: la última jugada de cada mapa trae el marcador de rondas al momento
        for ev in requests.get(D5_API + mid + "/live", headers=D5_H, timeout=20).json().get("data") or []:
            nm = ((ev.get("map") or {}).get("name") or "")
            if nm and nm not in ultimo and ev.get("scoreA") is not None:
                ultimo[nm] = (int(ev["scoreA"]), int(ev["scoreB"]))
    except (requests.RequestException, ValueError, TypeError):
        pass
    mapas, envivo = [], None
    for i, sc in enumerate(scores):
        nm = ((sc.get("map") or {}).get("mapName") or "")
        bonito = nm.replace("de_", "").title()
        if bonito.lower() in ("tba", "tbd", ""):
            bonito = ""  # mapa aún sin elegir
        a, b = int(sc.get("scoreA") or 0), int(sc.get("scoreB") or 0)
        if i >= jugados and nm in ultimo and sum(ultimo[nm]) > a + b:
            a, b = ultimo[nm]
        if giro:
            a, b = b, a
        if i < jugados:
            mapas.append([bonito, a, b])
        else:
            mapas.append([bonito, None, None])
            if i == jugados and not d.get("isFinished") and (a or b or nm in ultimo):
                envivo = {"n": i + 1, "mapa": bonito, "a": a, "b": b, "fuente": "DRAFT5"}
    if giro:
        sa, sb = sb, sa
    fin = bool(d.get("isFinished") or d.get("isOver"))
    return {"m": f"{sa}-{sb}", "mapas": mapas, "envivo": envivo, "fin": fin}



# ---------------------------------------------------------------- CS2: id del partido en HLTV (para el móvil)
# Los servidores de HLTV no dejan entrar a GitHub, pero el móvil sí puede abrir su "scorebot" (rondas al
# momento). Aquí solo se averigua el número del partido y de cada equipo en dust2.us (web hermana de HLTV).
_D2 = {"t": 0, "lista": []}


def _d2_lista() -> list:
    if time.time() - _D2["t"] > 300:
        try:
            t = requests.get("https://www.dust2.us/matches", headers={**UA, "Accept": "text/html"}, timeout=25).text
            lista = []
            for bloque in t.split('class="match-list-component')[1:]:
                mid = re.search(r'data-scorebot-match-id="(\d+)"', bloque)
                if not mid:
                    continue
                eq = re.findall(r'<span class="text-ellipsis">([^<]+)</span>', bloque)
                ids = re.findall(r'data-map-score-element="" data-scorebot-team-id="(\d+)"', bloque)
                url = re.search(r'href="(/matches/\d+/[^"]+)"', bloque)
                if len(eq) >= 2 and len(ids) >= 2 and url:
                    lista.append({"id": int(mid.group(1)), "n1": eq[0].strip(), "n2": eq[1].strip(), "t1": int(ids[0]), "t2": int(ids[1]),
                                  "url": url.group(1)})
            _D2["lista"], _D2["t"] = lista, time.time()
        except requests.RequestException:
            pass
    return _D2["lista"]


def hltv(local: str, visitante: str, terminado: bool = False) -> dict | None:
    for m in _d2_lista():
        d = parecido(m["n1"], local) + parecido(m["n2"], visitante)
        r = parecido(m["n1"], visitante) + parecido(m["n2"], local)
        if max(d, r) >= 1.5:
            return {"id": m["id"], "tl": m["t1"] if d >= r else m["t2"], "tv": m["t2"] if d >= r else m["t1"],
                    "_url": m["url"], "_giro": r > d}
    # Ya terminado: se busca en los resultados de dust2 (por el enlace "equipo1-vs-equipo2"; los más recientes primero)
    for mid, slug in (_d2_resultados() if terminado else []):
        if "-vs-" not in slug:
            continue
        a, b = slug.split("-vs-", 1)
        a, b = a.replace("-", " "), b.replace("-", " ")
        d = parecido(a, local) + parecido(b, visitante)
        r = parecido(a, visitante) + parecido(b, local)
        if max(d, r) >= 1.5:
            return {"id": int(mid), "tl": 0, "tv": 0, "_url": f"/matches/{mid}/{slug}", "_giro": r > d}
    return None


_D2R = {"t": 0, "l": []}


def _d2_resultados() -> list:
    if time.time() - _D2R["t"] > 600:
        try:
            t = requests.get("https://www.dust2.us/results", headers={**UA, "Accept": "text/html"}, timeout=25).text
            _D2R["l"] = list(dict.fromkeys(re.findall(r'href="/matches/(\d+)/([a-z0-9-]+)"', t)))
            _D2R["t"] = time.time()
        except requests.RequestException:
            pass
    return _D2R["l"]


_D2M: dict = {}
_HV: dict = {}  # partido -> datos de HLTV (para seguir leyendo sus mapas cuando ya ha terminado)


def mapas_d2(h: dict) -> dict:
    """Resultado de los mapas ya acabados según dust2.us/HLTV: {"cache": (13, 5)} desde el punto de vista del local."""
    c = _D2M.get(h["_url"])
    if c and time.time() - c[0] < 90:
        return c[1]
    out = {}
    try:
        t = requests.get("https://www.dust2.us" + h["_url"], headers={**UA, "Accept": "text/html"}, timeout=25).text
        for bloque in t.split('class="map-container-map-name">')[1:]:
            nombre = bloque.split("<", 1)[0].strip().lower()
            seg = bloque.split("map-container-map-name")[0]
            a = re.search(r'map-container-score-left">\s*(\d+)\s*<', seg)
            b = re.search(r'map-container-score-right">\s*(\d+)\s*<', seg)
            if nombre and a and b and ("map-won" in seg or "map-lost" in seg):
                x, y = int(a.group(1)), int(b.group(1))
                out[nombre] = (y, x) if h["_giro"] else (x, y)
    except requests.RequestException:
        pass
    _D2M[h["_url"]] = (time.time(), out)
    return out


# ---------------------------------------------------------------- Valorant: vlr.gg (rondas del mapa en juego)
_VLR = {"t": 0, "lista": []}


_VLRR = {"t": 0, "lista": []}
_VLR_FIN: dict = {}


def _vlr_bloques(t: str) -> list:
    """Partidos de un listado de vlr.gg: url, equipos, marcador y estado (LIVE, Completed, Upcoming)."""
    lista = []
    for bloque in re.split(r'<a href="(?=/\d+/)', t)[1:]:
        if "match-item" not in bloque[:300]:
            continue
        url = bloque.split('"', 1)[0]
        eq = [_limpio(x) for x in re.findall(r'match-item-vs-team-name">(.*?)</div>\s*</div>', bloque, re.S)]
        sc = re.findall(r'match-item-vs-team-score[^"]*">\s*([^<\s]*)\s*<', bloque)
        st = re.search(r'ml-status">\s*([^<]+?)\s*<', bloque)
        if len(eq) >= 2:
            lista.append({"url": url, "n1": eq[0], "n2": eq[1], "st": (st.group(1) if st else "").upper(),
                          "s1": sc[0] if sc else "", "s2": sc[1] if len(sc) > 1 else ""})
    return lista


def _vlr_resultados() -> list:
    if time.time() - _VLRR["t"] > 300:
        try:
            t = requests.get("https://www.vlr.gg/matches/results", headers={**UA, "Accept": "text/html", "Cache-Control": "no-cache"}, timeout=25, params={"_": int(time.time())}).text
            _VLRR["lista"], _VLRR["t"] = [x for x in _vlr_bloques(t) if x["st"].startswith("COMPLETED")], time.time()
        except requests.RequestException:
            pass
    return _VLRR["lista"]


def vlr_valorant(cand: list) -> dict:
    """Valorant: en directo y terminados desde vlr.gg (bo3.gg solo tiene Counter-Strike)."""
    res = {}
    val = [p for p in cand if "VAL" in (p.get("liga") or "") or "Valorant" in (p.get("liga") or "")]
    if not val:
        return res
    for x in _vlr_resultados():
        b = buscar(val, x["n1"], x["n2"])
        if not b or b[0]["clave"] in res or not (x["s1"].isdigit() and x["s2"].isdigit()):
            continue
        a, c = int(x["s1"]), int(x["s2"])
        if b[1]:
            a, c = c, a
        r = {"st": "post", "m": f"{a}-{c}", "det": "Final", "fuente": "vlr.gg"}
        try:
            v = _VLR_FIN.get(x["url"]) or vlr(b[0]["local"], b[0]["visitante"], url=x["url"], giro=b[1])
            if v:
                _VLR_FIN[x["url"]] = v
                r["mapas"] = v["mapas"]
        except Exception:  # noqa: BLE001
            pass
        res[b[0]["clave"]] = r
    for x in _vlr_lista():
        b = buscar(val, x["n1"], x["n2"])
        if not b or b[0]["clave"] in res:
            continue
        try:
            v = vlr(b[0]["local"], b[0]["visitante"], url=x["url"], giro=b[1])
        except Exception:  # noqa: BLE001
            v = None
        if v:
            r = {"st": "in", "m": v["m"], "mapas": v["mapas"], "det": f"Mapa {sum(int(z) for z in v['m'].split('-')) + 1}", "fuente": "vlr.gg"}
            if v["envivo"]:
                e = v["envivo"]
                r["envivo"], r["det"] = e, f"Mapa {e['n']} · {e['mapa']} {e['a']}-{e['b']}".replace("  ", " ")
            res[b[0]["clave"]] = r
    return res


def _vlr_lista() -> list:
    if time.time() - _VLR["t"] > 120:
        try:
            t = requests.get("https://www.vlr.gg/matches", headers={**UA, "Accept": "text/html", "Cache-Control": "no-cache"}, timeout=25, params={"_": int(time.time())}).text
            lista = []
            for bloque in t.split('class="wf-module-item match-item')[1:]:
                href = re.search(r'href="(/\d+/[^"]+)"', bloque) or re.search(r"^[^>]*?href=\"(/\d+/[^\"]+)\"", bloque)
                eq = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r'match-item-vs-team-name">\s*<div class="text-of">(.*?)</div>', bloque, re.S)]
                if href and len(eq) >= 2 and re.search(r'ml-status">\s*LIVE', bloque):
                    lista.append({"url": href.group(1), "n1": eq[0], "n2": eq[1]})
            _VLR["lista"], _VLR["t"] = lista, time.time()
        except requests.RequestException:
            pass
    return _VLR["lista"]


def _limpio(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def vlr(local: str, visitante: str, url: str | None = None, giro: bool = False) -> dict | None:
    """Mapas y rondas desde vlr.gg, desde el punto de vista del local."""
    m = {"url": url} if url else None
    for x in ([] if url else _vlr_lista()):
        d = parecido(x["n1"], local) + parecido(x["n2"], visitante)
        r = parecido(x["n1"], visitante) + parecido(x["n2"], local)
        if max(d, r) >= 1.5:
            m, giro = x, r > d
            break
    if not m:
        return None
    try:
        # con un parámetro que cambia: si no, vlr.gg/Cloudflare devuelve una copia vieja de la página (p. ej. de antes de empezar)
        t = requests.get("https://www.vlr.gg" + m["url"], headers={**UA, "Accept": "text/html", "Cache-Control": "no-cache"}, timeout=25,
                         params={"game": "all", "tab": "overview", "_": int(time.time())}).text
    except requests.RequestException:
        return None
    mapas, envivo, sa, sb = [], None, 0, 0
    for bloque in re.split(r'<div class="vm-stats-game\s*[^"]*" data-game-id="', t)[1:]:
        if bloque.startswith("all"):
            continue
        cab = bloque.split('class="vlr-rounds')[0]
        sc = re.findall(r'<div class="score([^"]*)"[^>]*>\s*(\d+)\s*</div>', cab)
        nm = re.search(r'class="map-name">.*?<span[^>]*>\s*([A-Za-z]+)', cab, re.S)
        nombre = nm.group(1) if nm else ""
        if len(sc) < 2:
            mapas.append([nombre, None, None])
            continue
        a, b = int(sc[0][1]), int(sc[1][1])
        gana_a, gana_b = "mod-win" in sc[0][0], "mod-win" in sc[1][0]
        if giro:
            a, b, gana_a, gana_b = b, a, gana_b, gana_a
        if gana_a or gana_b:
            mapas.append([nombre, a, b])
            sa, sb = sa + gana_a, sb + gana_b
        else:
            mapas.append([nombre, None, None])
            if envivo is None:
                envivo = {"n": len(mapas), "mapa": nombre, "a": a, "b": b, "fuente": "vlr.gg"}
    if not mapas:
        return None
    return {"m": f"{sa}-{sb}", "mapas": mapas, "envivo": envivo}


# ---------------------------------------------------------------- LoL: datos oficiales de Riot (lolesports)
LOL_H = {**UA, "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"}
_LOL = {"t": 0, "ev": []}


def lol(local: str, visitante: str) -> dict | None:
    """Partida en juego: asesinatos, oro, torres y dragones de cada equipo (punto de vista del local)."""
    if time.time() - _LOL["t"] > 60:
        try:
            j = requests.get("https://esports-api.lolesports.com/persisted/gw/getLive?hl=es-ES", headers=LOL_H, timeout=20).json()
            _LOL["ev"] = [e for e in ((j.get("data") or {}).get("schedule") or {}).get("events") or [] if e.get("match")]
            _LOL["t"] = time.time()
        except (requests.RequestException, ValueError):
            pass
    ev = None
    for e in _LOL["ev"]:
        tt = (e.get("match") or {}).get("teams") or []
        if len(tt) < 2:
            continue
        n1 = [tt[0].get("name", ""), tt[0].get("code", "")]
        n2 = [tt[1].get("name", ""), tt[1].get("code", "")]
        d = max(parecido(x, local) for x in n1) + max(parecido(x, visitante) for x in n2)
        r = max(parecido(x, visitante) for x in n1) + max(parecido(x, local) for x in n2)
        if max(d, r) >= 1.5:
            ev = e
            break
    if not ev:
        return None
    try:
        det = requests.get("https://esports-api.lolesports.com/persisted/gw/getEventDetails",
                           params={"hl": "es-ES", "id": ev["match"]["id"]}, headers=LOL_H, timeout=20).json()["data"]["event"]["match"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None
    nombres = {t["id"]: t.get("name", "") for t in det.get("teams") or []}
    juego = next((g for g in det.get("games") or [] if g.get("state") == "inProgress"), None)
    if not juego:
        return None
    desde = datetime.utcfromtimestamp((int(time.time()) - 60) // 10 * 10).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    try:
        w = requests.get(f"https://feed.lolesports.com/livestats/v1/window/{juego['id']}", params={"startingTime": desde},
                         headers=UA, timeout=20).json()
    except (requests.RequestException, ValueError):
        return None
    fr = (w.get("frames") or [None])[-1]
    if not fr:
        return None
    md = w.get("gameMetadata") or {}
    azul = nombres.get((md.get("blueTeamMetadata") or {}).get("esportsTeamId"), "")
    A, B = fr.get("blueTeam") or {}, fr.get("redTeam") or {}
    if parecido(azul, visitante) > parecido(azul, local):
        A, B = B, A
    k = lambda x: f"{(x or 0) / 1000:.1f}k"  # noqa: E731
    extra = (f"Oro {k(A.get('totalGold'))}–{k(B.get('totalGold'))} · Torres {A.get('towers', 0)}–{B.get('towers', 0)}"
             f" · Dragones {len(A.get('dragons') or [])}–{len(B.get('dragons') or [])}")
    if A.get("barons") or B.get("barons"):
        extra += f" · Barones {A.get('barons', 0)}–{B.get('barons', 0)}"
    return {"envivo": {"n": int(juego.get("number") or 1), "mapa": "", "a": int(A.get("totalKills") or 0),
                       "b": int(B.get("totalKills") or 0), "unidad": "asesinatos", "extra": extra, "fuente": "LoL Esports"}}


def esports(cand: list) -> dict:
    res = {}
    for estado in ("current", "finished"):
        try:
            j = requests.get("https://api.bo3.gg/api/v1/matches", headers=UA, timeout=25, params={
                "filter[matches.status][in]": estado, "page[limit]": 60, "sort": "-start_date", "with": "teams"}).json()
        except (requests.RequestException, ValueError):
            continue
        for m in j.get("results") or []:
            # bo3.gg es de Counter-Strike (discipline 1): solo para partidos de CS2 (si no, un "Wolves" de CS2
            # se colaba en un "Wolves" de Valorant)
            cs2 = [p for p in cand if "CS2" in (p.get("liga") or "")]
            x = buscar(cs2, (m.get("team1") or {}).get("name", ""), (m.get("team2") or {}).get("name", ""))
            if not x or x[0]["clave"] in res:
                continue
            a, b = int(m.get("team1_score") or 0), int(m.get("team2_score") or 0)
            if x[1]:
                a, b = b, a
            fin = estado == "finished"
            bo = int(m.get("bo_type") or 0)
            if bo and max(a, b) > bo // 2:
                fin = True  # la serie ya está decidida aunque la fuente no la haya cerrado
            r = {"st": "post" if fin else "in", "m": f"{a}-{b}", "det": "Final" if fin else f"Mapa {a + b + 1}"}
            # Mapa a mapa (nombre y rondas), desde el punto de vista del local de la app
            try:
                g = requests.get("https://api.bo3.gg/api/v1/games", headers=UA, timeout=20,
                                 params={"filter[games.match_id][eq]": m["id"]}).json().get("results") or []
                t1 = (m.get("team1") or {}).get("name", "")
                mapas = []
                for juego in sorted(g, key=lambda z: z.get("number") or 0):
                    w, l = juego.get("winner_clan_score"), juego.get("loser_clan_score")
                    if w is None and juego.get("status") == "upcoming":
                        mapas.append([(juego.get("map_name") or "").replace("de_", "").title(), None, None])
                        continue
                    wn = juego.get("winner_clan_name") or ""
                    gana1 = parecido(wn, t1) >= parecido(wn, (m.get("team2") or {}).get("name", ""))
                    s1, s2 = (w, l) if gana1 else (l, w)
                    if x[1]:
                        s1, s2 = s2, s1
                    mapas.append([(juego.get("map_name") or "").replace("de_", "").title(), s1, s2])
                # Mapas acabados sin marcador: el ganador sale del marcador de la serie
                fl = [i for i, z in enumerate(mapas) if z[1] is None and i < a + b]
                if fl:
                    ga = a - sum(1 for z in mapas if z[1] is not None and z[1] > z[2])
                    gb = b - sum(1 for z in mapas if z[1] is not None and z[2] > z[1])
                    if ga + gb == len(fl) and (ga == 0 or gb == 0):
                        for i in fl:
                            mapas[i][1:] = ["✓", ""] if ga else ["", "✓"]
                r["mapas"] = mapas
                # Mapa que se está jugando ahora (la fuente solo da el marcador al terminar cada mapa)
                if not fin:
                    for juego in g:
                        if juego.get("status") == "current" and juego.get("map_name"):
                            r["det"] = f"Mapa {juego.get('number') or a + b + 1} · {(juego.get('map_name') or '').replace('de_', '').title()}"
            except (requests.RequestException, ValueError, TypeError):
                pass
            # Counter-Strike: DRAFT5 da las rondas del mapa en juego (y suele ir por delante)
            if "CS2" in (x[0].get("liga") or ""):
                try:
                    d5 = draft5(x[0]["local"], x[0]["visitante"])
                except Exception:  # noqa: BLE001
                    d5 = None
                # Solo si DRAFT5 narra de verdad el partido y no va por detrás de bo3.gg
                if d5:
                    jd5 = sum(int(z) for z in d5["m"].split("-"))
                    if jd5 < a + b or not (jd5 or d5["envivo"] or d5["fin"]):
                        d5 = None
                if d5:
                    viejos = r.get("mapas") or []
                    for i, z in enumerate(d5["mapas"]):  # nombres que DRAFT5 aún no tiene
                        if not z[0] and i < len(viejos) and viejos[i][0]:
                            z[0] = viejos[i][0]
                    r["m"], r["mapas"] = d5["m"], d5["mapas"]
                    if d5["fin"] and not fin:
                        r["st"], r["det"] = "post", "Final"
                    elif d5["envivo"] and not fin:
                        e = d5["envivo"]
                        r["envivo"] = e
                        r["det"] = f"Mapa {e['n']} · {e['mapa']} {e['a']}-{e['b']}"
                    elif not fin:
                        n = sum(int(x) for x in d5["m"].split("-")) + 1
                        if n <= len(d5["mapas"]):
                            r["det"] = f"Mapa {n} · {d5['mapas'][n - 1][0]}"
                    r["fuente"] = "DRAFT5"
                try:  # HLTV/dust2: resultado de cada mapa (manda sobre bo3.gg) y, en directo, el móvil saca las rondas
                    h = _HV.get(x[0]["clave"]) if fin else None
                    h = h or hltv(x[0]["local"], x[0]["visitante"], terminado=fin)
                    if h:
                        _HV[x[0]["clave"]] = h  # al acabar desaparece de la portada de dust2: se recuerda
                        r["d2"] = [h["_url"], h["_giro"], h["id"], h["tl"], h["tv"]]
                        hechos = mapas_d2(h)
                        for z in r.get("mapas") or []:
                            k = (z[0] or "").lower()
                            if k in hechos:
                                z[1], z[2] = hechos[k]
                        if not fin and not r.get("envivo"):
                            r["hltv"] = {k: v for k, v in h.items() if not k.startswith("_")}
                except Exception:  # noqa: BLE001
                    pass
            liga = x[0].get("liga") or ""
            if not fin and ("VAL" in liga or "Valorant" in liga):
                try:
                    v = vlr(x[0]["local"], x[0]["visitante"])
                except Exception:  # noqa: BLE001
                    v = None
                if v and sum(int(z) for z in v["m"].split("-")) >= a + b:
                    viejos = r.get("mapas") or []
                    for i, z in enumerate(v["mapas"]):
                        if not z[0] and i < len(viejos):
                            z[0] = viejos[i][0]
                    r["m"], r["mapas"] = v["m"], v["mapas"] + viejos[len(v["mapas"]):]
                    if v["envivo"]:
                        e = v["envivo"]
                        r["envivo"], r["det"] = e, f"Mapa {e['n']} · {e['mapa']} {e['a']}-{e['b']}".replace("  ", " ")
                    r["fuente"] = "vlr.gg"
            if not fin and ("LOL" in liga or "League" in liga):
                try:
                    v = lol(x[0]["local"], x[0]["visitante"])
                except Exception:  # noqa: BLE001
                    v = None
                if v:
                    e = v["envivo"]
                    r["envivo"], r["det"] = e, f"Partida {e['n']} · {e['a']}-{e['b']} en asesinatos"
                    r["fuente"] = "LoL Esports"
            res[x[0]["clave"]] = r
    return res


# ---------------------------------------------------------------- notificaciones (app Android)
BOT = "https://victormoreno172-sys.github.io/picks-dorados/bot/datos.json"


def candidatos_todos(datos: dict, ahora: datetime) -> list[dict]:
    """Todos los partidos que se juegan ahora (cualquier deporte), con lo necesario para los avisos."""
    out = []
    for dia in datos.get("dias", []):
        for p in dia["partidos"]:
            dep = p.get("dep", "f")
            try:
                ini = datetime.fromisoformat(f"{dia['fecha']}T{p.get('hora') or '00:00'}").replace(tzinfo=TZ)
            except ValueError:
                continue
            if ini - timedelta(minutes=10) <= ahora <= ini + timedelta(hours=12 if dep == "e" else 5):
                fi = p.get("fi") or {}
                out.append({"clave": f"{dia['fecha']}|{p['local']}|{p['visitante']}", "fecha": dia["fecha"],
                            "local": p["local"], "visitante": p["visitante"], "liga": p.get("liga") or "", "dep": dep,
                            "slug": fi.get("slug") or "", "id": str(fi.get("id") or "")})
    return out


def espn(cands: list, ahora: datetime) -> dict:
    """Fútbol y NBA en ESPN (por el id del partido que ya tiene la app)."""
    por_slug: dict[str, dict] = {}
    for c in cands:
        if c["slug"] and c["id"] and (c["dep"] == "f" or c["slug"] == "nba"):
            por_slug.setdefault(c["slug"], {})[c["id"]] = c
    out = {}
    for slug, ids in por_slug.items():
        dep = "basketball" if slug == "nba" else "soccer"
        for f in {ahora.date(), (ahora - timedelta(hours=8)).date()}:
            try:
                j = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{dep}/{slug}/scoreboard",
                                 params={"dates": f"{f:%Y%m%d}"}, headers=UA, timeout=20).json()
            except (requests.RequestException, ValueError):
                continue
            for e in j.get("events") or []:
                c = ids.get(str(e.get("id")))
                if not c:
                    continue
                try:
                    comp = e["competitions"][0]
                    st = comp["status"]["type"].get("state")
                    eq = {x["homeAway"]: x for x in comp["competitors"]}
                    m = f"{int(eq['home'].get('score') or 0)}-{int(eq['away'].get('score') or 0)}" if st != "pre" else ""
                    out[c["clave"]] = {"st": st, "m": m, "det": comp["status"].get("displayClock") or ""}
                except (KeyError, IndexError, ValueError, TypeError):
                    continue
    return out


def tenis(cands: list) -> dict:
    """Tenis en ESPN: sets ganados por cada uno."""
    te = [c for c in cands if c["dep"] == "te"]
    if not te:
        return {}
    out = {}
    for tour in ("atp", "wta"):
        try:
            j = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard", headers=UA, timeout=20).json()
        except (requests.RequestException, ValueError):
            continue
        for ev in j.get("events") or []:
            for g in ev.get("groupings") or []:
                for c in g.get("competitions") or []:
                    try:
                        a, b = c["competitors"]
                        n1, n2 = a["athlete"]["displayName"], b["athlete"]["displayName"]
                        x = buscar(te, n1, n2)
                        if not x:
                            continue
                        st = c["status"]["type"].get("state")
                        la, lb = a.get("linescores") or [], b.get("linescores") or []
                        sa = sum(1 for u, v in zip(la, lb) if (u.get("value") or 0) > (v.get("value") or 0))
                        sb = sum(1 for u, v in zip(la, lb) if (v.get("value") or 0) > (u.get("value") or 0))
                        if st == "in" and la:  # el set en juego aún no cuenta
                            u, v = la[-1].get("value") or 0, lb[-1].get("value") or 0
                            if not (max(u, v) >= 6 and abs(u - v) >= 2) and not (max(u, v) == 7):
                                if u > v:
                                    sa -= 1
                                elif v > u:
                                    sb -= 1
                        if x[1]:
                            sa, sb = sb, sa
                        out[x[0]["clave"]] = {"st": st, "m": f"{max(sa, 0)}-{max(sb, 0)}" if st != "pre" else ""}
                    except (KeyError, ValueError, TypeError):
                        continue
    return out


def avisar_partidos(estados: dict, prev: dict, info: dict):
    import avisos
    for k, e in estados.items():
        c = info.get(k)
        if not c or not e:
            continue
        a = prev.get(k) or {}
        l, v, dep = c["local"], c["visitante"], c["dep"]
        datos = {"p": k}
        temas = lambda t: avisos.temas_partido(t, c["fecha"], l, v, c["liga"], dep)  # noqa: E731
        liga = avisos.liga_base(c["liga"])
        if e.get("st") == "in" and a.get("st") not in ("in", "post"):
            avisos.enviar(temas("i"), f"▶️ Empieza: {l} – {v}", liga, datos, k)
        if e.get("st") in ("in", "post") and a.get("st") == "in" and e.get("m") and a.get("m") and e["m"] != a["m"] and dep != "b":
            try:
                x1, y1 = (int(z) for z in a["m"].split("-"))
                x2, y2 = (int(z) for z in e["m"].split("-"))
            except ValueError:
                x1 = y1 = x2 = y2 = 0
            quien = l if x2 > x1 else v if y2 > y1 else ""
            if quien:
                ico, que = {"te": ("🎾", "Set para"), "e": ("🎮", "Mapa para")}.get(dep, ("⚽", "¡Gol de"))
                tit = f"{ico} {que} {quien}{'!' if dep == 'f' else ''}"
                det = f" ({e['det']})" if e.get("det") and dep == "f" else ""
                avisos.enviar(temas("g"), tit, f"{l} {e['m']} {v}{det} · {liga}", datos, k)
        if e.get("st") == "post" and a.get("st") != "post" and a:
            avisos.enviar(temas("f"), f"🏁 Final: {l} {e.get('m', '')} {v}", liga, datos, k)


def avisar_apuestas(bot: dict, estados: dict, avisados: dict):
    import avisos
    import historial
    for ap in bot.get("apuestas") or []:
        if "ok" in ap:
            continue
        k = avisos.clave_apuesta(ap)
        s = avisados.setdefault(k, {})
        if s.get("fin"):
            continue
        piernas = []
        for pi in ap.get("piernas") or []:
            e = None
            try:
                f = datetime.fromisoformat(pi["fecha"]).date()
                for d in (f, f - timedelta(days=1), f + timedelta(days=1)):
                    e = estados.get(f"{d.isoformat()}|{pi['local']}|{pi['visitante']}") or e
            except (KeyError, ValueError):
                pass
            piernas.append((pi, e))
        tema = [avisos.tema_apuesta(k)]
        texto = lambda pi: f"{pi['local']} – {pi['visitante']} · {pi['mercado']}"  # noqa: E731
        datos = {"vista": "misap"}
        if not s.get("ini") and any(e and e.get("st") in ("in", "post") for _, e in piernas):
            pi = next(pi for pi, e in piernas if e and e.get("st") in ("in", "post"))
            avisos.enviar(tema, f"🎟️ Empieza tu {ap.get('tipo', 'apuesta').lower()}", texto(pi), datos, "ap" + k[:40])
            s["ini"] = 1
        res = []
        for pi, e in piernas:
            r = None
            if e and e.get("st") == "post" and re.match(r"^\d+-\d+$", e.get("m") or ""):
                gl, gv = (int(z) for z in e["m"].split("-"))
                r = historial.acierta(pi["mercado"], gl, gv, pi["local"], pi["visitante"])
            res.append(r)
        cuota = f"{float(ap.get('cuota') or 0):.2f}".replace(".", ",")
        if any(r is False for r in res):
            pi = piernas[res.index(False)][0]
            avisos.enviar(tema, f"❌ Se ha caído tu {ap.get('tipo', 'apuesta').lower()}", texto(pi), datos, "ap" + k[:40])
            s["fin"] = 1
        elif res and all(r is True for r in res):
            avisos.enviar(tema, f"✅ ¡Ganada! {ap.get('tipo', 'Apuesta')} a {cuota}",
                          " + ".join(f"{pi['local']} – {pi['visitante']}" for pi, _ in piernas), datos, "ap" + k[:40])
            s["fin"] = 1


def publicar(contenido: dict):
    with open("directo.json", "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False)
    cmds = [["git", "add", "directo.json"], ["git", "commit", "-qm", "directo", "--allow-empty"],
            ["git", "push", "-qf", "origin", "HEAD:directo"]]
    for c in cmds:
        subprocess.run(c, check=False)


def main():
    # Rama aparte, un solo commit (se reescribe cada vez)
    subprocess.run(["git", "checkout", "-q", "--orphan", "directo-tmp"], check=False)
    subprocess.run(["git", "rm", "-rqf", "--cached", "."], check=False)
    inicio, datos, t_datos, ultimo, t_pub = time.time(), {}, 0, None, 0
    # Los partidos ya terminados se siguen publicando (con su resultado) hasta el día siguiente,
    # aunque hayan salido de la ventana de "en juego"; se recuperan de la vuelta anterior.
    finales: dict = {}
    try:
        previo = subprocess.run(["git", "show", "origin/directo:directo.json"], capture_output=True, text=True)
        if previo.returncode != 0:
            subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", "directo"], check=False)
            previo = subprocess.run(["git", "show", "FETCH_HEAD:directo.json"], capture_output=True, text=True)
        anterior = json.loads(previo.stdout or "{}")
        finales = {k: v for k, v in (anterior.get("res") or {}).items() if v.get("st") == "post"}
    except (ValueError, OSError):
        anterior, finales = {}, {}
    # Para no repetir avisos al empezar otra vuelta: estado de cada partido y apuestas ya avisadas
    previos = {**(anterior.get("res") or {}), **(anterior.get("push") or {})}
    for k, v in (anterior.get("res") or {}).items():  # partidos de CS2 ya vistos en HLTV
        d2 = v.get("d2")
        if isinstance(d2, list) and len(d2) == 5:
            _HV[k] = {"_url": d2[0], "_giro": d2[1], "id": d2[2], "tl": d2[3], "tv": d2[4]}
    avisados: dict = anterior.get("avisados") or {}
    bot, t_bot = {}, 0
    import avisos
    con_avisos = avisos.disponible()
    while time.time() - inicio < DURACION:
        ahora = datetime.now(TZ)
        if time.time() - t_datos > 600:
            try:
                datos = requests.get(DATOS, params={"t": int(time.time())}, timeout=30).json()
                t_datos = time.time()
            except (requests.RequestException, ValueError):
                pass
        cand = candidatos(datos, ahora)
        res = {}
        if cand["b"]:
            res.update(basket(cand["b"], ahora))
        if cand["e"]:
            res.update(esports(cand["e"]))
            try:  # Valorant (vlr.gg), que bo3.gg no tiene
                res.update(vlr_valorant(cand["e"]))
            except Exception as e:  # noqa: BLE001
                print("aviso vlr:", e)
        limite = (ahora - timedelta(days=1)).date().isoformat()
        finales = {k: v for k, v in finales.items() if k[:10] >= limite}
        finales.update({k: v for k, v in res.items() if v.get("st") == "post"})
        res = {**finales, **res}
        push, todos = {}, []
        if con_avisos:
            try:
                todos = candidatos_todos(datos, ahora)
                info = {c["clave"]: c for c in todos}
                push = {**espn(todos, ahora), **tenis(todos)}
                estados = {**res, **push}
                avisar_partidos(estados, previos, info)
                if time.time() - t_bot > 600:
                    try:
                        bot = requests.get(BOT, params={"t": int(time.time())}, timeout=30).json()
                        t_bot = time.time()
                    except (requests.RequestException, ValueError):
                        pass
                avisar_apuestas(bot, {**previos, **estados}, avisados)
                previos = {**previos, **{k: {"st": v.get("st"), "m": v.get("m")} for k, v in estados.items()}}
                limite2 = (ahora - timedelta(days=2)).date().isoformat()
                previos = {k: v for k, v in previos.items() if k[:10] >= limite2}
                avisados = {k: v for k, v in avisados.items() if k[:10] >= limite2}
            except Exception as e:  # noqa: BLE001
                print(f"  aviso notificaciones: {e}")
        # 23:30: aviso a los que juegan en la Arena de que ya están los partidos de mañana
        if con_avisos and ahora.strftime("%H:%M") >= "23:30":
            k_ar = ahora.date().isoformat() + "|arena"
            if k_ar not in avisados:
                try:
                    avisos.enviar(["arena"], "🏟️ Ya están los partidos de mañana",
                                  "Gánale a la app y HI-SCORE: haz tus pronósticos antes de que empiecen.", {"vista": "desafios"}, "arena")
                    avisados[k_ar] = 1
                    print("  aviso Arena enviado")
                except Exception as e:  # noqa: BLE001
                    print(f"  aviso Arena: {e}")
        contenido = {"ts": ahora.strftime("%H:%M:%S"), "res": res, "push": push, "avisados": avisados}
        firma = json.dumps([res, push, avisados], sort_keys=True, ensure_ascii=False)
        if firma != ultimo or (res and time.time() - t_pub > 150):  # y cada 2,5 min para que se vea que está vivo
            publicar(contenido)
            ultimo, t_pub = firma, time.time()
            print(f"{contenido['ts']} {len(res)} marcadores ({len(cand['b'])} basket, {len(cand['e'])} esports en juego)")
        hay = cand["b"] or cand["e"] or (con_avisos and todos)
        time.sleep(60 if hay else 300)


if __name__ == "__main__":
    main()
