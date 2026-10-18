"""
Fases y rondas de los torneos de esports (datos de bo3.gg).

Cada torneo de bo3.gg trae sus "stages" (Group A, Group B, Playoffs, Decider...) con sus
rondas (Opening matches, Semifinal, Grand final...) y los partidos de cada una. Aquí se
ordenan en fases numeradas, en español:
  Fase 1 · Grupos (Grupo A, Grupo B)  ->  Fase 2 · Playoffs (Semifinales, Tercer puesto, Final)
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

import config

URL = "https://api.bo3.gg/api/v1/tournaments/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept": "application/json"}
TZ = ZoneInfo(config.ZONA_HORARIA)
_CACHE: dict[str, dict | None] = {}


def slug_de(nombre: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def torneo(slug: str) -> dict | None:
    """Torneo de bo3.gg con sus fases, rondas y partidos (una vez por ejecución)."""
    if not slug:
        return None
    if slug in _CACHE:
        return _CACHE[slug]
    dato = None
    for intento in range(2):
        try:
            r = requests.get(URL + slug, headers=UA, timeout=30)
            if r.status_code == 429:
                time.sleep(10)
                continue
            if r.ok:
                dato = r.json()
            break
        except (requests.RequestException, ValueError):
            time.sleep(2)
    _CACHE[slug] = dato if isinstance(dato, dict) and dato.get("stages") else None
    time.sleep(0.3)
    return _CACHE[slug]


# ---------------------------------------------------------------- nombres en español
_FASES = [
    (r"^play-?offs?$", "Playoffs"), (r"swiss", "Fase suiza"), (r"play-?in", "Play-In"),
    (r"^(group stage|groups?)$", "Grupos"), (r"knockout", "Eliminatorias"), (r"last chance", "Última oportunidad"),
    (r"^main event$", "Fase principal"), (r"opening stage", "Fase de apertura"), (r"elimination stage", "Fase de eliminación"),
    (r"^bracket( stage)?$", "Cuadro final"), (r"^finals?$", "Finales"), (r"^stage (\d+)$", r"Etapa \1"),
    (r"^round robin$", "Liguilla"), (r"^regular season$", "Fase regular"), (r"qualifier", "Clasificatorio"),
]


def fase_es(t: str) -> str:
    for pat, es in _FASES:
        if re.search(pat, t, re.I):
            return re.sub(pat, es, t, flags=re.I) if "\\1" in es else es
    return t


def ronda_es(t: str) -> str:
    t = (t or "").strip()
    x = t.lower()
    m = re.match(r"(upper|lower)( bracket)?\s+(.*)", x)
    if m:
        lado = "cuadro de ganadores" if m.group(1) == "upper" else "cuadro de perdedores"
        resto = ronda_es(m.group(3))
        return f"{resto} del {lado}" if resto in ("Final", "Semifinal", "Semifinales", "Cuartos de final") else f"{resto} · {lado}"
    reglas = [
        (r"^grand final", "Final"), (r"^finals?$", "Final"), (r"semi", "Semifinales"), (r"quarter", "Cuartos de final"),
        (r"round of 16|eighth", "Octavos de final"), (r"3rd|third", "Tercer puesto"), (r"opening", "Primera ronda"),
        (r"winners?'? match", "Partido de ganadores"), (r"elimination match", "Partido de eliminación"),
        (r"decider", "Partido decisivo"), (r"tiebreak", "Desempate"), (r"qualification match", "Partido por la clasificación"),
    ]
    for pat, es in reglas:
        if re.search(pat, x):
            return es
    m = re.match(r"round (\d+)(.*)", x)
    if m:
        return f"Ronda {m.group(1)}{m.group(2)}"
    return t[:1].upper() + t[1:]


# ---------------------------------------------------------------- estructura del torneo
def estructura(slug: str, nombre: str) -> dict | None:
    """{"fases": [...], "stage": {id: (n, nombre_fase, grupo)}, "ronda": {id: (nombre, orden)}}"""
    T = torneo(slug)
    if not T:
        return None
    nombre_bo3 = T.get("name") or nombre
    grupos: dict[str, dict] = {}
    deciders = []
    for st in T.get("stages") or []:
        titulo = (st.get("title") or "").replace(nombre_bo3, "").strip(" -:·") or (st.get("title") or "")
        g = re.match(r"(?i)^(.*?)\s*group\s+([a-z]|\d{1,2}|[a-z]\d)$", titulo)
        if g:
            clave, grupo = (g.group(1).strip() or "Grupos"), f"Grupo {g.group(2).upper()}"
        elif re.search(r"(?i)decider|3rd place|third place", titulo):
            deciders.append(st)
            continue
        else:
            clave, grupo = titulo, ""
            if "swiss" in str(st.get("format_type") or "").lower():
                clave = "Swiss Stage"
        f = grupos.setdefault(clave, {"ini": "9999", "seq": 999, "stages": []})
        f["ini"] = min(f["ini"], st.get("start_date") or "9999")
        f["seq"] = min(f["seq"], st.get("sequence_number") or 999)
        f["stages"].append((st, grupo))
    if deciders:
        if grupos:
            ultima = max(grupos.values(), key=lambda f: f["ini"])
            ultima["stages"] += [(st, "") for st in deciders]
        else:
            grupos["Tercer puesto"] = {"ini": "9999", "seq": 999, "stages": [(st, "") for st in deciders]}
    orden = sorted(grupos.items(), key=lambda kv: (kv[1]["ini"], kv[1]["seq"]))
    out = {"fases": [], "stage": {}, "ronda": {}}
    for i, (clave, f) in enumerate(orden, 1):
        nombre_fase = f"Fase {i} · {fase_es(clave)}"
        out["fases"].append({"n": i, "nombre": nombre_fase, "stages": f["stages"],
                             "grupos": sorted({g for _, g in f["stages"] if g}),
                             "tipo": "grupo" if any(g for _, g in f["stages"]) or "swiss" in clave.lower()
                             or any(str(st.get("format_type") or "").lower() in ("group", "swiss") for st, _ in f["stages"]) else "cuadro"})
        for st, grupo in f["stages"]:
            out["stage"][st.get("id")] = (i, nombre_fase, grupo)
            for r in st.get("rounds") or []:
                out["ronda"][r.get("id")] = (ronda_es(r.get("name") or ""), r.get("round_index") or 0)
    return out


def etiqueta(slug: str, nombre: str, stage_id, round_id) -> str:
    """Texto para un partido: "Fase 2 · Playoffs · Final"."""
    E = estructura(slug, nombre) if slug else None
    if not E or stage_id not in E["stage"]:
        return ""
    _, fase, grupo = E["stage"][stage_id]
    ronda = (E["ronda"].get(round_id) or ("", 0))[0]
    return " · ".join(x for x in (fase, grupo, ronda) if x)


def partidos(E: dict):
    """Partidos de cada fase: [(fase, grupo, ronda, orden_ronda, match), ...]"""
    for f in E["fases"]:
        for st, grupo in f["stages"]:
            for r in st.get("rounds") or []:
                for m in r.get("matches") or []:
                    yield f, grupo, ronda_es(r.get("name") or ""), r.get("round_index") or 0, m


def fecha_hora(iso: str) -> tuple[str, str]:
    try:
        d = datetime.fromisoformat(iso).astimezone(TZ)
        return d.date().isoformat(), d.strftime("%H:%M")
    except (TypeError, ValueError):
        return "", ""
