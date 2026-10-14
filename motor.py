"""Junta todo: baja datos, entrena un modelo por liga y analiza los partidos."""
from __future__ import annotations

from datetime import date, timedelta

import config
import datos
from analisis import Analisis, analizar
from modelo import ModeloDixonColes


def poner_cuotas(p: datos.PartidoProximo, hoy: date):
    """Sustituye las cuotas medias por las de Winamax cuando las hay."""
    if p.cuotas:
        p.casa = "media del mercado"
    try:
        import cuotas
        ev = cuotas.instancia(hoy).buscar(p.liga, p.fecha, p.local, p.visitante)
    except Exception as e:
        print(f"  aviso cuotas: {e}")
        return
    if ev:
        p.cuotas = {**p.cuotas, **ev.cuotas}
        p.casa = ev.casa


def analizar_dias(desde: date, n_dias: int = 1) -> dict[date, list[Analisis]]:
    """Analiza los partidos de `desde` y los n_dias-1 siguientes."""
    print(f"Preparando predicciones desde {desde} ({n_dias} días)...")
    historicos = {liga: datos.historico(liga, desde) for liga in config.LIGAS}
    if not any(historicos.values()):
        # Sin datos es mejor fallar: así la app sigue mostrando la última versión buena.
        raise RuntimeError("No se pudo descargar ningún resultado histórico.")
    equipos = {l: sorted({p.local for p in h} | {p.visitante for p in h}) for l, h in historicos.items()}
    import historial
    for h in historicos.values():
        for p in h:
            historial.anotar(p.fecha, p.local, p.visitante, p.goles_local, p.goles_visitante)

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
            poner_cuotas(p, desde)
            a = analizar(p, modelos[p.liga])
            if a:
                lista.append(a)
            else:
                print(f"  sin historial suficiente: {p.local} - {p.visitante}")
        salida[dia] = lista

    # Competiciones europeas (si algo falla, la app sigue con las ligas)
    try:
        import europa
        proximos, modelo_eu = europa.preparar(desde, n_dias)
        for pe in proximos:
            p = datos.PartidoProximo(pe.comp, pe.fecha, pe.hora, pe.local, pe.visitante)
            poner_cuotas(p, desde)
            a = analizar(p, modelo_eu)
            if a:
                salida.setdefault(pe.fecha, []).append(a)
            else:
                print(f"  sin datos suficientes: {pe.local} - {pe.visitante}")
    except Exception as e:
        import traceback
        print(f"  aviso: competiciones europeas no disponibles: {e}")
        traceback.print_exc()

    for dia in salida:
        salida[dia].sort(key=lambda a: (a.partido.hora or "99", a.partido.liga))
    return salida


def analizar_dia(dia: date) -> list[Analisis]:
    return analizar_dias(dia, 1)[dia]
