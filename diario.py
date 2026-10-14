"""
Lo que se ejecuta solo cada mañana en GitHub:
  1. Calcula las predicciones de la próxima semana.
  2. Genera la app web (carpeta web/).
  3. Si hay token de Telegram y ENVIAR_TELEGRAM=true, publica el resumen de hoy en el canal.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import web
from analisis import resumen_del_dia
from motor import analizar_dias

hoy = datetime.now(ZoneInfo(config.ZONA_HORARIA)).date()
import datos
datos.diagnostico_proximos()
por_dia = analizar_dias(hoy, 7)
# La app enseña hoy y los 3 próximos días que tengan partidos (así en parones o
# entre semana no aparece vacía).
con_partidos = [d for d in sorted(por_dia) if d != hoy and por_dia[d]][:3]
web.escribir(web.a_json({d: por_dia[d] for d in [hoy] + con_partidos}, hoy))

if (os.getenv("ENVIAR_TELEGRAM", "").lower() == "true" and por_dia[hoy]
        and config.TELEGRAM_TOKEN and config.TELEGRAM_CANAL):
    import bot
    for msg in resumen_del_dia(por_dia[hoy], hoy):
        bot.enviar(config.TELEGRAM_CANAL, msg)
    print("Resumen enviado a Telegram")
