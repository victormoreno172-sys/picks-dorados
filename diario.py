"""
Lo que se ejecuta solo cada mañana en GitHub:
  1. Calcula las predicciones de la próxima semana.
  2. Genera la app web (carpeta web/).
  3. Si hay token de Telegram y ENVIAR_TELEGRAM=true, publica el resumen de hoy en el canal.
"""
import builtins
import os
import time
from datetime import datetime

# Cada línea del registro lleva los segundos desde el inicio (para ver qué tarda)
_T0, _print = time.time(), builtins.print
builtins.print = lambda *a, **k: _print(f"[{time.time() - _T0:4.0f}s]", *a, **k)
from zoneinfo import ZoneInfo

import config
import web
from analisis import resumen_del_dia
from motor import analizar_dias

hoy = datetime.now(ZoneInfo(config.ZONA_HORARIA)).date()
import datos
datos.diagnostico_proximos()
por_dia = analizar_dias(hoy, 7)

# Baloncesto (si falla, la app sigue con el fútbol)
try:
    import baloncesto
    for d, lista in baloncesto.analizar_dias(hoy, 7).items():
        por_dia.setdefault(d, []).extend(lista)
except Exception as e:
    print(f"aviso: baloncesto no disponible: {e}")

# Tenis: ATP y WTA
try:
    import tenis
    for d, lista in tenis.analizar_dias(hoy, 7).items():
        por_dia.setdefault(d, []).extend(lista)
except Exception as e:
    print(f"aviso: tenis no disponible: {e}")

# Esports: CS2, Valorant y LoL (si falla, la app sigue con lo demás)
try:
    import esports
    for d, lista in esports.analizar_dias(hoy, 7).items():
        por_dia.setdefault(d, []).extend(lista)
except Exception as e:
    print(f"aviso: esports no disponible: {e}")


def deporte(a):
    return a.partido.deporte or ("b" if config.es_baloncesto(a.partido.liga) else "f")


# La app enseña hoy y, de cada deporte, los 3 próximos días que tengan partidos
# (así en parones o entre semana no aparece vacía).
def proximos_con(dep):
    return [d for d in sorted(por_dia) if d != hoy and any(deporte(a) == dep for a in por_dia[d])][:3]

dias = sorted({hoy, *proximos_con("f"), *proximos_con("b"), *proximos_con("te"), *proximos_con("e")})
for d in dias:
    por_dia.setdefault(d, []).sort(key=lambda a: (a.partido.hora or "99", a.partido.liga))
datos_app = web.a_json({d: por_dia[d] for d in dias}, hoy)

# Ficha de cada partido: escudos, estadio, alineaciones, clasificación y forma (ESPN)
try:
    import ficha
    ficha.recuperar_empezados(datos_app, "previo.json")
    ficha.enriquecer(datos_app)
except Exception as e:
    import traceback
    print(f"aviso: fichas no disponibles: {e}")
    traceback.print_exc()

# Resultados que aún no han llegado por los CSV (fútbol europeo del fin de semana): de ESPN
try:
    import ficha
    ficha.resultados_pendientes()
except Exception as e:
    print(f"aviso: resultados pendientes: {e}")

# Historial de aciertos (si falla, la app sale igual sin esa pantalla)
try:
    import historial
    datos_app["historial"] = historial.actualizar(por_dia, hoy)
except Exception as e:
    import traceback
    print(f"aviso: historial no disponible: {e}")
    traceback.print_exc()

# Resultados de los últimos 10 días (para los desafíos: el móvil los necesita aunque el partido ya no salga en la app)
try:
    import json as _json
    from datetime import timedelta as _td
    try:
        with open("previo.json", encoding="utf-8") as _f:
            _prev = _json.load(_f)
    except (OSError, ValueError):
        _prev = {}
    _res = dict(_prev.get("resultados") or {})
    for _fuente in (_prev, datos_app):
        for _d in _fuente.get("dias", []):
            for _p in _d.get("partidos", []):
                _r = _p.get("res") or {}
                if _r.get("st") == "post" and _r.get("m"):
                    _res[f'{_d["fecha"]}|{_p["local"]}|{_p["visitante"]}'] = _r["m"]
    # Partidos que acaban después de la última actualización de su día (los de las 21:00) se quedaban
    # sin resultado: al día siguiente ya no salen en la app. Se apuntan como "sinres" y se buscan después.
    _sin = {k: v for k, v in (_prev.get("sinres") or {}).items() if k not in _res}
    for _fuente in (_prev, datos_app):
        for _d in _fuente.get("dias", []):
            if _d["fecha"] > hoy.isoformat():
                continue
            for _p in _d.get("partidos", []):
                _k = f'{_d["fecha"]}|{_p["local"]}|{_p["visitante"]}'
                if _k not in _res:
                    _sin[_k] = {"dep": _p.get("dep", "f"), "liga": _p.get("liga") or "", "hora": _p.get("hora") or ""}
    # El primero que se perdió así (antes de este arreglo); se borra solo a los 4 días
    if "2026-10-22|Ajax|Atalanta" not in _res:
        _sin.setdefault("2026-10-22|Ajax|Atalanta", {"dep": "f", "liga": "Conference League", "hora": "21:00"})
    _lim4 = (hoy - _td(days=4)).isoformat()
    _sin = {k: v for k, v in _sin.items() if k[:10] >= _lim4}
    try:
        import ficha as _fi
        from datetime import date as _date
        _cache: dict = {}
        for _k, _v in list(_sin.items()):
            _f, _l, _vi = _k.split("|", 2)
            _fecha = _date.fromisoformat(_f)
            _r = None
            _ds = _fi.SLUGS.get(_v["liga"])
            if _ds:
                _evs = []
                for _dd in (_fecha - _td(days=1), _fecha, _fecha + _td(days=1)):
                    if (*_ds, _dd) not in _cache:
                        _cache[(*_ds, _dd)] = _fi._eventos(*_ds, _dd)
                    _evs += _cache[(*_ds, _dd)]
                _e = _fi._emparejar({"local": _l, "visitante": _vi, "hora": _v["hora"]}, _fecha, _evs)
                _r = (_e or {}).get("estado")
            elif _v["dep"] in ("b", "te", "e"):
                _r = _fi._resultado_propio({"dep": _v["dep"], "local": _l, "visitante": _vi}, _f)
            if _r and _r.get("st") == "post" and _r.get("m"):
                _res[_k] = _r["m"]
                _sin.pop(_k)
        print(f"  resultados recuperados de días anteriores: quedan {len(_sin)} sin resultado")
    except Exception as e:  # noqa: BLE001
        print(f"aviso: resultados de días anteriores: {e}")
    datos_app["sinres"] = _sin
    _lim = (hoy - _td(days=10)).isoformat()
    datos_app["resultados"] = {k: v for k, v in _res.items() if k[:10] >= _lim}
    print(f"  resultados guardados para los desafíos: {len(datos_app['resultados'])}")
except Exception as e:
    print(f"aviso: resultados de los desafíos: {e}")

web.escribir(datos_app)

# Pestaña Ligas: clasificaciones, jornadas y equipos (un archivo por liga)
try:
    import ligas
    print(f"[{datetime.now():%H:%M:%S}] ligas")
    ligas.escribir(datos_app)
    web.escribir(datos_app)  # otra vez, ya con la posición de cada equipo en su liga o ranking
except Exception as e:
    import traceback
    print(f"aviso: ligas no disponibles: {e}")
    traceback.print_exc()

# (21/10) El bot de apuestas se ha quitado: ahora cada uno apunta sus apuestas en la app (Estadísticas).

