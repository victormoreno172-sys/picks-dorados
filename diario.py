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

web.escribir(datos_app)

# Pestaña Ligas: clasificaciones, jornadas y equipos (un archivo por liga)
try:
    import ligas
    print(f"[{datetime.now():%H:%M:%S}] ligas")
    ligas.escribir(datos_app)
except Exception as e:
    import traceback
    print(f"aviso: ligas no disponibles: {e}")
    traceback.print_exc()

# Apuestas del día por Telegram (pasadas las 00:00) y banca simulada
try:
    import apuestas
    import bot_web
    bot_web.escribir(apuestas.actualizar(por_dia))
except Exception as e:
    import traceback
    print(f"aviso: apuestas no disponibles: {e}")
    traceback.print_exc()

