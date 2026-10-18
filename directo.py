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
            if ini - timedelta(minutes=10) <= ahora <= ini + timedelta(hours=8 if dep == "e" else 5):
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
                envivo = {"n": i + 1, "mapa": bonito, "a": a, "b": b}
    if giro:
        sa, sb = sb, sa
    fin = bool(d.get("isFinished") or d.get("isOver"))
    return {"m": f"{sa}-{sb}", "mapas": mapas, "envivo": envivo, "fin": fin}


def esports(cand: list) -> dict:
    res = {}
    for estado in ("current", "finished"):
        try:
            j = requests.get("https://api.bo3.gg/api/v1/matches", headers=UA, timeout=25, params={
                "filter[matches.status][in]": estado, "page[limit]": 60, "sort": "-start_date", "with": "teams"}).json()
        except (requests.RequestException, ValueError):
            continue
        for m in j.get("results") or []:
            x = buscar(cand, (m.get("team1") or {}).get("name", ""), (m.get("team2") or {}).get("name", ""))
            if not x or x[0]["clave"] in res:
                continue
            a, b = int(m.get("team1_score") or 0), int(m.get("team2_score") or 0)
            if x[1]:
                a, b = b, a
            fin = estado == "finished"
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
                    gana1 = parecido(juego.get("winner_clan_name") or "", t1) >= 0.85
                    s1, s2 = (w, l) if gana1 else (l, w)
                    if x[1]:
                        s1, s2 = s2, s1
                    mapas.append([(juego.get("map_name") or "").replace("de_", "").title(), s1, s2])
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
                if d5:
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
            res[x[0]["clave"]] = r
    return res


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
        finales = {k: v for k, v in (json.loads(previo.stdout or "{}").get("res") or {}).items() if v.get("st") == "post"}
    except (ValueError, OSError):
        finales = {}
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
        limite = (ahora - timedelta(days=1)).date().isoformat()
        finales = {k: v for k, v in finales.items() if k[:10] >= limite}
        finales.update({k: v for k, v in res.items() if v.get("st") == "post"})
        res = {**finales, **res}
        contenido = {"ts": ahora.strftime("%H:%M:%S"), "res": res}
        if res != ultimo or (res and time.time() - t_pub > 150):  # y cada 2,5 min para que se vea que está vivo
            publicar(contenido)
            ultimo, t_pub = res, time.time()
            print(f"{contenido['ts']} {len(res)} marcadores ({len(cand['b'])} basket, {len(cand['e'])} esports en juego)")
        time.sleep(60 if (cand["b"] or cand["e"]) else 300)


if __name__ == "__main__":
    main()
