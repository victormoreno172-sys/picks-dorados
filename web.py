"""
Genera la app web (la carpeta `web/`) que se ve en el móvil.

  python web.py           -> datos reales de hoy y los 2 días siguientes
  python web.py --demo    -> datos de ejemplo, sin internet
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import config
from analisis import Analisis

CARPETA = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(CARPETA, "web")
DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

CABECERA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b1711">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Picks Dorados">
<meta name="mobile-web-app-capable" content="yes">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icono.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="icono.png">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}</style>
</head>
<body>
"""

ICONO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" rx="112" fill="#0b1711"/>
<circle cx="256" cy="256" r="150" fill="none" stroke="#f2bf3e" stroke-width="28"/>
<text x="256" y="300" text-anchor="middle" font-family="Arial Narrow,Arial,sans-serif" font-weight="700" font-size="150" fill="#f2bf3e">%</text>
</svg>"""

MANIFEST = {
    "name": "Picks Dorados", "short_name": "Picks", "lang": "es",
    "start_url": "./", "display": "standalone",
    "background_color": "#0b1711", "theme_color": "#0b1711",
    "icons": [{"src": "icono.svg", "sizes": "any", "type": "image/svg+xml"},
              {"src": "icono.png", "sizes": "512x512", "type": "image/png"}],
}


def etiqueta(dia: date, hoy: date) -> str:
    if dia == hoy:
        return "Hoy"
    if dia == hoy + timedelta(days=1):
        return "Mañana"
    return DIAS_SEMANA[dia.weekday()]


def a_json(por_dia: dict[date, list[Analisis]], hoy: date, demo: bool = False) -> dict:
    ahora = datetime.now(ZoneInfo(config.ZONA_HORARIA))
    dias = []
    for d, lista in sorted(por_dia.items()):
        partidos = []
        for a in lista:
            p = a.partido
            partidos.append({
                "liga": config.nombre_liga(p.liga).split(" ", 1)[-1],
                "hora": p.hora, "local": p.local, "visitante": p.visitante,
                "gl": round(a.goles_local, 2), "gv": round(a.goles_visitante, 2),
                "marcador": a.marcador, "pm": round(float(a.prob_marcador or 0), 4),
                "dep": "b" if config.es_baloncesto(p.liga) else "f",
                "picks": [{"m": k.mercado, "p": round(float(k.prob), 4),
                           "c": float(k.cuota) if k.cuota else None,
                           "d": bool(k.dorado), "v": bool(k.valor)} for k in a.picks],
            })
        dias.append({"fecha": d.isoformat(), "fecha_corta": d.strftime("%d/%m"),
                     "etiqueta": etiqueta(d, hoy), "partidos": partidos})
    return {"generado": ahora.strftime("%d/%m %H:%M"), "umbral": config.UMBRAL_DORADO,
            "demo": demo, "dias": dias}


def html(datos: dict, documento_completo: bool = True) -> str:
    with open(os.path.join(CARPETA, "plantilla.html"), encoding="utf-8") as f:
        cuerpo = f.read()
    # json seguro dentro de <script>
    js = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    cuerpo = cuerpo.replace("__DATOS__", js)
    return (CABECERA + cuerpo + "\n</body>\n</html>\n") if documento_completo else cuerpo


def _icono_png(ruta: str):
    """PNG para iPhone (no acepta SVG como icono de pantalla de inicio)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    im = Image.new("RGB", (512, 512), "#0b1711")
    dr = ImageDraw.Draw(im)
    dr.ellipse((106, 106, 406, 406), outline="#f2bf3e", width=28)
    try:
        fuente = ImageFont.truetype("DejaVuSans-Bold.ttf", 150)
    except OSError:
        fuente = ImageFont.load_default()
    dr.text((256, 262), "%", fill="#f2bf3e", font=fuente, anchor="mm")
    im.save(ruta)


def escribir(datos: dict, carpeta: str = SALIDA):
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "index.html"), "w", encoding="utf-8") as f:
        f.write(html(datos))
    with open(os.path.join(carpeta, "datos.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    with open(os.path.join(carpeta, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=2)
    with open(os.path.join(carpeta, "icono.svg"), "w", encoding="utf-8") as f:
        f.write(ICONO_SVG)
    _icono_png(os.path.join(carpeta, "icono.png"))
    print(f"App generada en {carpeta}/index.html")


def datos_demo() -> dict:
    import numpy as np

    from analisis import analizar
    from datos import PartidoProximo
    from demo import cuotas_simuladas, liga_simulada
    from modelo import ModeloDixonColes

    partidos, _ = liga_simulada()
    modelo = ModeloDixonColes().ajustar(partidos)
    rng = np.random.default_rng(3)
    hoy = datetime.now(ZoneInfo(config.ZONA_HORARIA)).date()
    cruces = {
        0: [("SP1", "Atlético Norte", "Cádiz Arena", "16:15"), ("SP1", "Real Costa", "Granada Río", "18:30"),
            ("E0", "Betis Sol", "Rayo Monte", "20:00"), ("SP1", "Osasuna Roca", "Getafe Llano", "21:00"),
            ("I1", "Sporting Lago", "Levante Mar", "20:45")],
        1: [("D1", "Unión Sierra", "Mallorca Isla", "18:30"), ("SP1", "Deportivo Valle", "Atlético Norte", "21:00")],
        2: [("SP1", "Racing Puerto", "Real Costa", "14:00"), ("E0", "Celta Brisa", "Oviedo Nube", "16:00"),
            ("F1", "CD Meseta", "Elche Palma", "21:00")],
    }
    por_dia = {}
    for k, lista in cruces.items():
        d = hoy + timedelta(days=k)
        por_dia[d] = [analizar(PartidoProximo(lg, d, h, l, v, cuotas_simuladas(modelo, l, v, rng)), modelo)
                      for lg, l, v, h in lista]

    # Baloncesto de ejemplo
    import baloncesto as b
    from tests_baloncesto import liga_simulada as basket_simulada
    juegos, _, _ = basket_simulada(5)
    nombres = {f"E{i}": n for i, n in enumerate(
        ["Halcones Norte", "Toros Valle", "Delfines Costa", "Lobos Sierra", "Águilas Puerto", "Linces Meseta",
         "Osos Lago", "Zorros Río", "Cóndores Isla", "Tigres Monte", "Búhos Llano", "Ciervos Bosque",
         "Panteras Sol", "Gacelas Mar", "Jabalíes Roca", "Leones Arena"])}
    mb = b.ModeloBaloncesto(xi=0.0).ajustar(juegos, hasta=hoy)
    for k, lista in {0: [("ACB", "E0", "E5", "18:00"), ("EL", "E3", "E1", "20:45")],
                     1: [("NBA", "E7", "E2", "02:00"), ("ACB", "E9", "E14", "21:00")]}.items():
        d = hoy + timedelta(days=k)
        for comp, l, v, h in lista:
            j = b.Juego(comp, d, h, l, v, nombres[l], nombres[v])
            j.comp = "ACB"  # el modelo de ejemplo solo conoce una liga
            a = b.analizar_juego(j, mb)
            a.partido.liga = comp
            por_dia.setdefault(d, []).append(a)
    return a_json(por_dia, hoy, demo=True)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        escribir(datos_demo())
    else:
        from motor import analizar_dias
        hoy = datetime.now(ZoneInfo(config.ZONA_HORARIA)).date()
        escribir(a_json(analizar_dias(hoy, 3), hoy))
