"""
Bot de Telegram.

  python bot.py            -> arranca el bot (responde comandos y publica cada día)
  python bot.py --ahora    -> publica el resumen de hoy en el canal y termina

Comandos dentro de Telegram:
  /hoy         resumen de los partidos de hoy
  /partido N   todos los mercados del partido número N
  /ayuda       explicación
"""
from __future__ import annotations

import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

import config
from analisis import detalle_partido, resumen_del_dia
from motor import analizar_dia

API = "https://api.telegram.org/bot{token}/{metodo}"
TZ = ZoneInfo(config.ZONA_HORARIA)

AYUDA = (
    "⚽ <b>Cómo funciona</b>\n\n"
    "Cada día calculo, para cada partido, la probabilidad de cada mercado "
    "(1X2, más/menos goles, ambos marcan…).\n\n"
    "Uso un modelo estadístico (Dixon-Coles) entrenado con los resultados de las últimas "
    "temporadas y lo combino con las cuotas del mercado.\n\n"
    f"🟡 Dorado: probabilidad de al menos {config.UMBRAL_DORADO:.0%}.\n"
    "💎 Valor: nuestra probabilidad es claramente mayor que la que indica la cuota.\n\n"
    "/hoy · /partido N\n\n"
    "<i>Ninguna predicción es segura. Juega con responsabilidad. Solo mayores de 18.</i>"
)

_cache: dict[date, list] = {}


def hoy() -> date:
    return datetime.now(TZ).date()


def analisis_de(dia: date):
    if dia not in _cache:
        _cache.clear()
        _cache[dia] = analizar_dia(dia)
    return _cache[dia]


def llamar(metodo: str, **params):
    r = requests.post(API.format(token=config.TELEGRAM_TOKEN, metodo=metodo), json=params, timeout=60)
    datos = r.json()
    if not datos.get("ok"):
        print(f"Telegram error en {metodo}: {datos}")
    return datos


def enviar(chat, texto: str):
    llamar("sendMessage", chat_id=chat, text=texto, parse_mode="HTML", disable_web_page_preview=True)


def publicar_resumen(chat):
    dia = hoy()
    for msg in resumen_del_dia(analisis_de(dia), dia):
        enviar(chat, msg)


def responder(chat, texto: str):
    partes = texto.strip().split()
    cmd = partes[0].split("@")[0].lower() if partes else ""
    if cmd in ("/start", "/ayuda", "/help"):
        enviar(chat, AYUDA)
    elif cmd == "/hoy":
        enviar(chat, "⏳ Calculando...")
        publicar_resumen(chat)
    elif cmd == "/partido":
        lista = analisis_de(hoy())
        try:
            n = int(partes[1])
            enviar(chat, detalle_partido(lista[n - 1]))
        except (IndexError, ValueError):
            enviar(chat, f"Escribe /partido seguido de un número del 1 al {len(lista)}. Ej: /partido 1")
    else:
        enviar(chat, "No entiendo ese comando. Prueba /hoy o /ayuda")


def bucle():
    print("Bot en marcha. Ctrl+C para parar.")
    offset, ultimo_dia_publicado = None, None
    while True:
        # 1) Publicación diaria automática
        ahora = datetime.now(TZ)
        if (config.TELEGRAM_CANAL and ahora.strftime("%H:%M") >= config.HORA_PUBLICACION
                and ultimo_dia_publicado != ahora.date()):
            try:
                publicar_resumen(config.TELEGRAM_CANAL)
                print(f"Resumen publicado {ahora:%d/%m %H:%M}")
            except Exception as e:  # que un fallo no tumbe el bot
                print(f"Error publicando: {e}")
            ultimo_dia_publicado = ahora.date()

        # 2) Mensajes de usuarios
        try:
            res = llamar("getUpdates", offset=offset, timeout=30)
            for u in res.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                if msg.get("text"):
                    try:
                        responder(msg["chat"]["id"], msg["text"])
                    except Exception as e:
                        print(f"Error respondiendo: {e}")
        except requests.RequestException as e:
            print(f"Sin conexión ({e}), reintento en 10 s")
            time.sleep(10)


if __name__ == "__main__":
    if not config.TELEGRAM_TOKEN:
        sys.exit("Falta TELEGRAM_TOKEN en el archivo .env (mira el README).")
    if "--ahora" in sys.argv:
        if not config.TELEGRAM_CANAL:
            sys.exit("Falta TELEGRAM_CANAL en el archivo .env")
        publicar_resumen(config.TELEGRAM_CANAL)
    else:
        bucle()
