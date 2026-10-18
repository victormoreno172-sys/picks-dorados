"""App del bot (web/bot/): banca, gráfica y estadísticas de las apuestas que manda el bot."""
from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import web

CARPETA = os.path.join(web.SALIDA, "bot")
MANIFEST = {"name": "Bot Dorado", "short_name": "Bot Dorado", "lang": "es", "start_url": "./", "scope": "./",
            "display": "standalone", "background_color": "#04060a", "theme_color": "#04060a",
            "icons": [{"src": "icono.svg", "sizes": "any", "type": "image/svg+xml"},
                      {"src": "icono.png", "sizes": "512x512", "type": "image/png"}]}


def html(datos: dict) -> str:
    with open(os.path.join(web.CARPETA, "plantilla_bot.html"), encoding="utf-8") as f:
        cuerpo = f.read()
    js = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    cabecera = web.CABECERA.replace("Picks Dorados", "Bot Dorado").replace("#0b1711", "#04060a")
    return cabecera + cuerpo.replace("__DATOS__", js) + "\n</body>\n</html>\n"


def escribir(b: dict, carpeta: str = CARPETA):
    os.makedirs(carpeta, exist_ok=True)
    datos = {"generado": datetime.now(ZoneInfo(config.ZONA_HORARIA)).strftime("%d/%m %H:%M"),
             "inicial": b["inicial"], "apuestas": b["apuestas"]}
    with open(os.path.join(carpeta, "index.html"), "w", encoding="utf-8") as f:
        f.write(html(datos))
    with open(os.path.join(carpeta, "datos.json"), "w", encoding="utf-8") as f:  # para "Mis apuestas" en Partidos
        json.dump(datos, f, ensure_ascii=False)
    with open(os.path.join(carpeta, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=2)
    with open(os.path.join(carpeta, "icono.svg"), "w", encoding="utf-8") as f:
        f.write(web.ICONO_SVG.replace("#f2bf3e", "#6fdc9f") if "#f2bf3e" in web.ICONO_SVG else web.ICONO_SVG)
    web._icono_png(os.path.join(carpeta, "icono.png"))
    print(f"App del bot generada en {carpeta}/index.html")
