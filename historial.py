"""
Historial de aciertos.

Cada ejecución:
  1. Guarda los picks destacados de los partidos que aún no se han jugado.
  2. Busca el resultado real de los partidos pendientes y corrige cada pick (acierto/fallo).
  3. Calcula estadísticas para la pantalla "Aciertos" de la app.

El historial vive en historial/historial.json (rama "historial" del repositorio).
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import date, timedelta

import config

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial", "historial.json")

# Resultados reales que van apareciendo en las fuentes: (fecha, local, visitante) -> (gl, gv)
RESULTADOS: dict[tuple[str, str, str], tuple[int, int]] = {}


def anotar(fecha: date, local: str, visitante: str, gl: int, gv: int):
    RESULTADOS[(fecha.isoformat(), local, visitante)] = (int(gl), int(gv))


# ------------------------------------------------------------------ acierto
def acierta(mercado: str, gl: int, gv: int, local: str = "", visitante: str = "") -> bool | None:
    """¿Se cumplió el mercado con este resultado? None si no se sabe corregir.
    Con los nombres también corrige tenis y esports (sets / mapas / partidas)."""
    t = gl + gv
    m = mercado
    if local and visitante:
        unidad = r"(?:sets|mapas|partidas)"
        if m == f"Gana {local}":
            return gl > gv
        if m == f"Gana {visitante}":
            return gv > gl
        r = re.match(rf"(Más|Menos) de ([\d.]+) {unidad}$", m)
        if r:
            linea = float(r.group(2))
            return t > linea if r.group(1) == "Más" else t < linea
        for nombre, margen in ((local, gl - gv), (visitante, gv - gl)):
            r = re.fullmatch(rf"{re.escape(nombre)} ([+-][\d.]+) {unidad}", m)
            if r:
                return margen + float(r.group(1)) > 0
        r = re.fullmatch(rf"Resultado {re.escape(local)} (\d+)-(\d+) {re.escape(visitante)}", m)
        if r:
            return (gl, gv) == (int(r.group(1)), int(r.group(2)))
    tabla = {
        "Gana local (1)": gl > gv, "Empate (X)": gl == gv, "Gana visitante (2)": gl < gv,
        "Local o empate (1X)": gl >= gv, "Visitante o empate (X2)": gl <= gv, "No hay empate (12)": gl != gv,
        "Ambos marcan: Sí": gl > 0 and gv > 0, "Ambos marcan: No": not (gl > 0 and gv > 0),
        "Local marca": gl > 0, "Visitante marca": gv > 0,
        "Gana local": gl > gv, "Gana visitante": gv > gl,
    }
    if m in tabla:
        return tabla[m]
    r = re.match(r"(Más|Menos) de ([\d.]+) (goles|puntos)", m)
    if r:
        linea = float(r.group(2))
        return t > linea if r.group(1) == "Más" else t < linea
    r = re.match(r"Hándicap (local|visitante) ([+-][\d.]+)", m)
    if r:
        margen = (gl - gv) if r.group(1) == "local" else (gv - gl)
        return margen + float(r.group(2)) > 0
    return None


# ---------------------------------------------------------------- guardar
def cargar() -> dict:
    try:
        with open(RUTA, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"partidos": {}}


def guardar(h: dict):
    os.makedirs(os.path.dirname(RUTA), exist_ok=True)
    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, separators=(",", ":"))


def registrar(h: dict, por_dia: dict, hoy: date):
    """Guarda (o actualiza) los picks de los partidos de hoy en adelante."""
    n = 0
    for dia, lista in por_dia.items():
        if dia < hoy:
            continue
        for a in lista:
            p = a.partido
            clave = f"{dia.isoformat()}|{p.liga}|{p.local}|{p.visitante}"
            previo = h["partidos"].get(clave)
            if previo and previo.get("res"):
                continue
            picks = [{"m": k.mercado, "p": round(float(k.prob), 4),
                      "c": float(k.cuota) if k.cuota and not k.estimada else None,
                      "d": bool(k.dorado), "v": bool(k.valor)}
                     for k in a.picks if k.dorado or (k.cuota and not k.estimada and k.prob >= 0.5)]
            if not picks:
                continue
            dep = p.deporte or ("b" if config.es_baloncesto(p.liga) else "f")
            h["partidos"][clave] = {"f": dia.isoformat(), "dep": dep,
                                    "liga": p.liga, "l": p.local, "v": p.visitante, "picks": picks, "res": None}
            n += 1
    print(f"  historial: {n} partidos guardados o actualizados")


def corregir(h: dict, hoy: date):
    """Rellena el resultado de los partidos ya jugados."""
    hechos = anulados = 0
    for clave, e in list(h["partidos"].items()):
        f = date.fromisoformat(e["f"])
        if e.get("res"):
            if (hoy - f).days > 3:
                continue
            # Últimos días: se vuelve a comprobar por si el resultado era provisional
            e["res"] = None
            for k in e["picks"]:
                k.pop("ok", None)
        if f > hoy:
            continue
        res = None
        for d in (f, f - timedelta(days=1), f + timedelta(days=1)):  # tolera cambios de fecha por zona horaria
            res = RESULTADOS.get((d.isoformat(), e["l"], e["v"]))
            if res:
                break
        if res:
            e["res"] = list(res)
            for k in e["picks"]:
                ok = acierta(k["m"], *res, e["l"], e["v"])
                if ok is not None:
                    k["ok"] = ok
            hechos += 1
        elif (hoy - f).days > 12:  # aplazado o sin resultado en las fuentes
            del h["partidos"][clave]
            anulados += 1
    print(f"  historial: {hechos} partidos corregidos, {anulados} descartados sin resultado")


# ------------------------------------------------------------ estadísticas
def _bloque(picks) -> dict:
    n = len(picks)
    ok = sum(k["ok"] for k in picks)
    con_cuota = [k for k in picks if k.get("c")]
    beneficio = sum((k["c"] - 1) if k["ok"] else -1 for k in con_cuota)
    return {"n": n, "ok": ok, "prob": round(sum(k["p"] for k in picks) / n, 3) if n else None,
            "nc": len(con_cuota), "roi": round(beneficio / len(con_cuota), 3) if con_cuota else None}


def resumen(h: dict, hoy: date) -> dict:
    corregidos = [e for e in h["partidos"].values() if e.get("res")]
    planos = []
    for e in corregidos:
        for k in e["picks"]:
            if "ok" in k:
                planos.append({**k, "f": e["f"], "dep": e["dep"], "liga": e["liga"]})

    def ventana(dias):
        return [k for k in planos if (hoy - date.fromisoformat(k["f"])).days <= dias] if dias else planos

    out = {"desde": min((e["f"] for e in h["partidos"].values()), default=None),
           "pendientes": sum(1 for e in h["partidos"].values() if not e.get("res")),
           "periodos": {}}
    for nombre, dias in (("7d", 7), ("30d", 30), ("todo", 0)):
        ks = ventana(dias)
        out["periodos"][nombre] = {
            "dorados": _bloque([k for k in ks if k["d"]]),
            "valor": _bloque([k for k in ks if k["v"]]),
            "f": _bloque([k for k in ks if k["d"] and k["dep"] == "f"]),
            "b": _bloque([k for k in ks if k["d"] and k["dep"] == "b"]),
        }
    # Por competición (30 días, solo dorados)
    por_liga = defaultdict(list)
    for k in ventana(30):
        if k["d"]:
            por_liga[k["liga"]].append(k)
    out["ligas"] = sorted(({"liga": config.nombre_liga(l).split(" ", 1)[-1], **_bloque(v)}
                           for l, v in por_liga.items()), key=lambda x: -x["n"])
    # Calibración: lo que dijimos frente a lo que pasó
    tramos = defaultdict(list)
    for k in planos:
        tramos[min(int(k["p"] * 20) * 5, 95)].append(k["ok"])
    out["calibracion"] = [{"desde": t, "n": len(v), "real": round(sum(v) / len(v), 3)}
                          for t, v in sorted(tramos.items()) if t >= 50 and len(v) >= 3]
    # Picks con cuota real (para recalcular los rojos con los umbrales que elija cada uno)
    out["con_cuota"] = [[k["f"], k["dep"], round(k["p"], 3), k["c"], int(k["ok"])]
                        for k in ventana(60) if k.get("c")]
    # Últimos picks destacados corregidos, para la lista de "últimos resultados"
    recientes = sorted((e for e in corregidos), key=lambda e: e["f"], reverse=True)
    ultimos = []
    for e in recientes:
        for k in sorted(e["picks"], key=lambda k: -k["p"]):
            if "ok" in k and (k["d"] or k.get("c")):
                ultimos.append({"f": e["f"], "dep": e["dep"], "liga": config.nombre_liga(e["liga"]).split(" ", 1)[-1],
                                "l": e["l"], "v": e["v"], "res": e["res"], "m": k["m"], "p": k["p"],
                                "c": k.get("c"), "d": k["d"], "ok": k["ok"]})
                break  # solo el pick principal de cada partido
        if len(ultimos) >= 40:
            break
    out["ultimos"] = ultimos
    return out


def actualizar(por_dia: dict, hoy: date) -> dict:
    h = cargar()
    corregir(h, hoy)
    registrar(h, por_dia, hoy)
    # Se guardan 400 días como máximo
    limite = (hoy - timedelta(days=400)).isoformat()
    h["partidos"] = {k: v for k, v in h["partidos"].items() if v["f"] >= limite}
    guardar(h)
    return resumen(h, hoy)
