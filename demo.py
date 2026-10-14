"""
Demo SIN internet ni Telegram: crea una liga simulada, entrena el modelo y
muestra en pantalla el mensaje que enviaría el bot.

  python demo.py
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import numpy as np

from analisis import analizar, detalle_partido, resumen_del_dia
from datos import PartidoProximo
from modelo import ModeloDixonColes, Partido

EQUIPOS = ["Atlético Norte", "Real Costa", "Unión Sierra", "Deportivo Valle", "Racing Puerto",
           "Sporting Lago", "CD Meseta", "Celta Brisa", "Betis Sol", "Rayo Monte",
           "Getafe Llano", "Osasuna Roca", "Elche Palma", "Girona Torre", "Alavés Viento",
           "Mallorca Isla", "Levante Mar", "Oviedo Nube", "Granada Río", "Cádiz Arena"]


def liga_simulada(semilla: int = 7, temporadas: int = 3):
    rng = np.random.default_rng(semilla)
    ataque = rng.normal(0, 0.3, len(EQUIPOS))
    defensa = rng.normal(0, 0.22, len(EQUIPOS))
    ataque[0], defensa[0] = 0.6, -0.45   # un "gigante" goleador
    ataque[1], defensa[1] = 0.45, -0.3
    base, campo = 0.12, 0.25
    partidos, dia = [], date(2026 - temporadas, 8, 15)
    for _ in range(temporadas):
        for _ronda in range(2):
            for _jornada in range(len(EQUIPOS) - 1):
                orden = rng.permutation(len(EQUIPOS))
                for k in range(0, len(EQUIPOS), 2):
                    h, a = orden[k], orden[k + 1]
                    gl = rng.poisson(np.exp(base + ataque[h] + defensa[a] + campo))
                    gv = rng.poisson(np.exp(base + ataque[a] + defensa[h]))
                    partidos.append(Partido(dia, EQUIPOS[h], EQUIPOS[a], int(gl), int(gv)))
                dia += timedelta(days=7)
        dia += timedelta(days=60)
    reales = {e: (base + ataque[i], defensa[i]) for i, e in enumerate(EQUIPOS)}
    return partidos, reales


def cuotas_simuladas(modelo, local, visitante, rng):
    """Cuotas como las de una casa: probabilidad + ruido + 6% de margen."""
    from modelo import mercados
    p = mercados(modelo.tabla_marcadores(local, visitante))
    out = {}
    for grupo in (["Gana local (1)", "Empate (X)", "Gana visitante (2)"],
                  ["Más de 2.5 goles", "Menos de 2.5 goles"]):
        ruido = np.array([p[m] for m in grupo]) * rng.normal(1, 0.06, len(grupo))
        ruido = ruido / ruido.sum() * 1.06
        out.update({m: round(1 / r, 2) for m, r in zip(grupo, ruido)})
    return out


def sin_html(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t)


if __name__ == "__main__":
    partidos, _ = liga_simulada()
    hoy = partidos[-1].fecha + timedelta(days=7)
    modelo = ModeloDixonColes().ajustar(partidos, hasta=hoy)
    rng = np.random.default_rng(1)
    cruces = [("Atlético Norte", "Cádiz Arena", "16:15"), ("Real Costa", "Granada Río", "18:30"),
              ("Betis Sol", "Rayo Monte", "21:00"), ("Osasuna Roca", "Getafe Llano", "21:00")]
    lista = []
    for l, v, h in cruces:
        p = PartidoProximo("SP1", hoy, h, l, v, cuotas_simuladas(modelo, l, v, rng))
        lista.append(analizar(p, modelo))

    print("=" * 60)
    for m in resumen_del_dia(lista, hoy):
        print(sin_html(m))
    print("=" * 60)
    print("Respuesta a /partido 1:\n")
    print(sin_html(detalle_partido(lista[0])))
