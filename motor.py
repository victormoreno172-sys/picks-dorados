"""Junta todo: baja datos, entrena un modelo por liga y analiza los partidos."""
from __future__ import annotations

from datetime import date, timedelta

import config
import datos
from analisis import Analisis, analizar
from modelo import ModeloDixonColes


def analizar_dias(desde: date, n_dias: int = 1) -> dict[date, list[Analisis]]:
    """Analiza los partidos de `desde` y los n_dias-1 siguientes."""
    print(f"Preparando predicciones desde {desde} ({n_dias} días)...")
    historicos = {liga: datos.historico(liga, desde) for liga in config.LIGAS}
    if not any(historicos.values()):
        # Sin datos es mejor fallar: así la app sigue mostrando la última versión buena.
        raise RuntimeError("No se pudo descargar ningún resultado histórico.")
    equipos = {l: sorted({p.local for p in h} | {p.visitante for p in h}) for l, h in historicos.items()}

    modelos: dict[str, ModeloDixonColes] = {}
    salida: dict[date, list[Analisis]] = {}
    for k in range(n_dias):
        dia = desde + timedelta(days=k)
        partidos = datos.partidos_del_dia(dia, equipos)
        print(f"  {dia}: {len(partidos)} partidos")
        lista = []
        for p in partidos:
            if p.liga not in modelos:
                try:
                    modelos[p.liga] = ModeloDixonColes().ajustar(historicos[p.liga], hasta=desde)
                except ValueError as e:
                    print(f"  {p.liga}: {e}")
                    continue
            if p.liga not in modelos:
                continue
            a = analizar(p, modelos[p.liga])
            if a:
                lista.append(a)
            else:
                print(f"  sin historial suficiente: {p.local} - {p.visitante}")
        salida[dia] = lista
    return salida


def analizar_dia(dia: date) -> list[Analisis]:
    return analizar_dias(dia, 1)[dia]
