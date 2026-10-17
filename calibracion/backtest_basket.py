"""
Backtest del basket europeo con resultados reales (se ejecuta en GitHub, donde están los datos).
Cada semana se reentrena el modelo solo con partidos anteriores y se predice la semana siguiente.
Mide el error en margen y total, y cuánto habría que corregir (factor del margen y suma al total).
"""
import os, sys, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, timedelta
import numpy as np
from scipy.stats import norm
import baloncesto as bb

hoy = date.today()
juegos = [j for j in bb.europa(hoy, 0) if j.jugado]
print("partidos jugados:", len(juegos), "desde", min(j.fecha for j in juegos))
inicio = hoy - timedelta(days=330)


def backtest(xi, reg, desde=inicio, hasta=hoy, verbose=False):
    filas = []
    d = desde
    while d < hasta:
        semana = [j for j in juegos if d <= j.fecha < d + timedelta(days=7)]
        if semana:
            try:
                m = bb.ModeloBaloncesto(xi, reg).ajustar(juegos, hasta=d)
            except ValueError:
                d += timedelta(days=7); continue
            for j in semana:
                if m.conoce(j.local_id) and m.conoce(j.visit_id):
                    pl, pv = m.esperado(j)
                    filas.append((pl - pv, pl + pv, j.pl - j.pv, j.pl + j.pv, j.comp, j.fecha, m.sd_margen))
        d += timedelta(days=7)
    a = np.array([f[:4] for f in filas], float)
    return a, filas


import builtins, io, contextlib
mejor = None
for xi, reg in itertools.product((0.002, 0.004, 0.007), (0.5, 2, 4, 10)):
    with contextlib.redirect_stdout(io.StringIO()):
        a, filas = backtest(xi, reg)
    pm, pt, rm, rt = a.T
    k = (pm @ rm) / (pm @ pm)               # factor del margen que mejor ajusta
    s = np.mean(rt - pt)                    # lo que falta en el total
    e_m, e_t = np.mean(np.abs(rm - pm)), np.mean(np.abs(rt - pt))
    e_m2, e_t2 = np.mean(np.abs(rm - k * pm)), np.mean(np.abs(rt - pt - s))
    acierto = np.mean((pm > 0) == (rm > 0))
    print(f"xi={xi} reg={reg:4}: n={len(a)}  error margen {e_m:5.2f} (corregido x{k:.2f}: {e_m2:5.2f})  "
          f"error total {e_t:5.2f} (corregido {s:+.1f}: {e_t2:5.2f})  acierta ganador {acierto:.1%}")
    if mejor is None or e_m2 + e_t2 < mejor[0]:
        mejor = (e_m2 + e_t2, xi, reg, k, s)
print("MEJOR:", mejor)
_, xi, reg, k, s = mejor
with contextlib.redirect_stdout(io.StringIO()):
    a, filas = backtest(xi, reg)
pm, pt, rm, rt = a.T
# principio de temporada (septiembre-noviembre) frente al resto
mes = np.array([f[5].month for f in filas])
ini = np.isin(mes, (9, 10, 11))
for nombre, msk in (("inicio temporada", ini), ("resto", ~ini)):
    if msk.sum() > 30:
        kk = (pm[msk] @ rm[msk]) / (pm[msk] @ pm[msk])
        print(f"  {nombre}: n={msk.sum()} factor margen {kk:.2f}  falta total {np.mean(rt[msk]-pt[msk]):+.1f}")
for c in sorted({f[4] for f in filas}):
    msk = np.array([f[4] == c for f in filas])
    if msk.sum() > 30:
        kk = (pm[msk] @ rm[msk]) / (pm[msk] @ pm[msk])
        print(f"  {c}: n={msk.sum()} factor margen {kk:.2f}  falta total {np.mean(rt[msk]-pt[msk]):+.1f}  error total {np.mean(np.abs(rt[msk]-pt[msk])):.1f}")
# calibración de probabilidades de ganar (con la corrección)
sd = np.array([f[6] for f in filas])
p = norm.sf(0, loc=k * pm, scale=sd)
for lo in (0.5, 0.6, 0.7, 0.8, 0.9):
    msk = (np.maximum(p, 1 - p) >= lo) & (np.maximum(p, 1 - p) < lo + 0.1)
    if msk.sum() > 20:
        fav = np.where(p >= 0.5, rm > 0, rm < 0)
        print(f"  favorito {lo:.0%}-{lo+0.1:.0%}: n={msk.sum()} dijo {np.mean(np.maximum(p,1-p)[msk]):.1%} pasó {np.mean(fav[msk]):.1%}")
