"""
Backtest: ¿las probabilidades del modelo se cumplen de verdad?

Simula el pasado sin hacer trampas: para cada jornada entrena SOLO con los
partidos anteriores y predice los siguientes. Luego compara lo predicho con
lo que pasó.

  python backtest.py SP1          -> LaLiga real (descarga datos)
  python backtest.py --demo       -> con una liga simulada (sin internet)
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, timedelta

import numpy as np

import config
from modelo import ModeloDixonColes, Partido, mercados

REFIT_DIAS = 14  # reentrenar cada 2 semanas (más rápido que cada día, casi igual de preciso)


def resultado_mercado(mercado: str, gl: int, gv: int) -> bool:
    t = gl + gv
    if mercado == "Gana local (1)": return gl > gv
    if mercado == "Empate (X)": return gl == gv
    if mercado == "Gana visitante (2)": return gl < gv
    if mercado == "Local o empate (1X)": return gl >= gv
    if mercado == "Visitante o empate (X2)": return gl <= gv
    if mercado == "No hay empate (12)": return gl != gv
    if mercado.startswith("Más de"): return t > float(mercado.split()[2])
    if mercado.startswith("Menos de"): return t < float(mercado.split()[2])
    if mercado == "Ambos marcan: Sí": return gl > 0 and gv > 0
    if mercado == "Ambos marcan: No": return not (gl > 0 and gv > 0)
    if mercado == "Local marca": return gl > 0
    if mercado == "Visitante marca": return gv > 0
    raise ValueError(mercado)


def backtest(partidos: list[Partido], desde: date) -> dict:
    partidos = sorted(partidos, key=lambda p: p.fecha)
    preds = []  # (mercado, prob, acertó)
    modelo, fecha_modelo = None, None
    for p in partidos:
        if p.fecha < desde:
            continue
        if modelo is None or (p.fecha - fecha_modelo).days >= REFIT_DIAS:
            modelo = ModeloDixonColes().ajustar(partidos, hasta=p.fecha)
            fecha_modelo = p.fecha
        if not (modelo.conoce(p.local) and modelo.conoce(p.visitante)):
            continue
        for m, prob in mercados(modelo.tabla_marcadores(p.local, p.visitante)).items():
            preds.append((m, prob, resultado_mercado(m, p.goles_local, p.goles_visitante)))
    return informe(preds)


def informe(preds) -> dict:
    tramos = defaultdict(lambda: [0, 0, 0.0])  # n, aciertos, suma prob
    for _, prob, ok in preds:
        t = min(int(prob * 10), 9)
        tramos[t][0] += 1
        tramos[t][1] += ok
        tramos[t][2] += prob

    dorados = [(m, p, ok) for m, p, ok in preds
               if p >= config.UMBRAL_DORADO and m not in config.MERCADOS_TRIVIALES]
    probs = np.array([p for _, p, _ in preds])
    oks = np.array([ok for _, _, ok in preds], dtype=float)

    print("\nCALIBRACIÓN (lo que dijo el modelo vs. lo que pasó)")
    print(f"{'Tramo':>10} {'Picks':>7} {'Predicho':>9} {'Real':>7}")
    for t in sorted(tramos):
        n, a, s = tramos[t]
        print(f"{t*10:>4}-{t*10+10:<3}% {n:>7} {s/n:>8.1%} {a/n:>7.1%}")

    res = {"brier": float(np.mean((probs - oks) ** 2)), "n": len(preds)}
    if dorados:
        acierto = np.mean([ok for *_, ok in dorados])
        media = np.mean([p for _, p, _ in dorados])
        res.update(dorados=len(dorados), acierto_dorados=float(acierto), prob_media_dorados=float(media))
        print(f"\nPICKS DORADOS: {len(dorados)} · prometían {media:.1%} de media · acertaron {acierto:.1%}")
        por_mercado = defaultdict(list)
        for m, p, ok in dorados:
            por_mercado[m].append(ok)
        for m, v in sorted(por_mercado.items(), key=lambda kv: -len(kv[1])):
            print(f"   {m:<26} {len(v):>5} picks · {np.mean(v):.1%} acierto")
    print(f"\nBrier score: {res['brier']:.4f} (más bajo = mejor)")
    return res


if __name__ == "__main__":
    if "--demo" in sys.argv:
        from demo import liga_simulada
        partidos, _ = liga_simulada()
        desde = partidos[len(partidos) * 2 // 3].fecha
    else:
        import datos
        liga = sys.argv[1] if len(sys.argv) > 1 else "SP1"
        hoy = date.today()
        partidos = datos.historico(liga, hoy)
        desde = hoy - timedelta(days=365)
        print(f"{config.LIGAS[liga][0]}: {len(partidos)} partidos, test desde {desde}")
    backtest(partidos, desde)
