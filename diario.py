"""
Lo que se ejecuta solo cada mañana en GitHub:
  1. Calcula las predicciones de hoy y los 2 días siguientes.
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
por_dia = analizar_dias(hoy, 3)
web.escribir(web.a_json(por_dia, hoy))

if os.getenv("ENVIAR_TELEGRAM", "").lower() == "true" and config.TELEGRAM_TOKEN and config.TELEGRAM_CANAL:
    import bot
    for msg in resumen_del_dia(por_dia[hoy], hoy):
        bot.enviar(config.TELEGRAM_CANAL, msg)
    print("Resumen enviado a Telegram")
