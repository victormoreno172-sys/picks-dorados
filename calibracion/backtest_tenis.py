"""
Calibración del modelo de tenis (Elo general + superficie) con el último año de partidos de ESPN.

Recorre los partidos en orden: antes de cada partido predice con lo que sabía hasta ese día y
después actualiza. Mide:
  - acierto del ganador (log-loss, Brier y tabla de calibración por tramos)
  - los mercados de sets que salen de esa probabilidad (2-0, más de 2.5 sets, +1.5 sets)
y prueba combinaciones de parámetros para elegir la mejor.

    python calibracion/backtest_tenis.py
"""
from __future__ import annotations

import itertools
import json
import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tenis  # noqa: E402


def esperado(a, b):
    return 1 / (1 + 10 ** ((b - a) / 400))


def recorrer(partidos, a=250.0, e=0.4, w=0.5, minimo=8, desde=None):
    """Devuelve [(p_j1, gana1, sets, s1, s2, superficie, fecha)] de los partidos predichos."""
    gen, sup, n, ns = {}, {}, {}, {}
    k = lambda m: a / (m + 5) ** e  # noqa: E731
    out = []
    for p in partidos:
        s = tenis.superficie(p.torneo, p.fecha)
        g1, g2 = gen.get(p.j1, 1500), gen.get(p.j2, 1500)
        k1, k2 = (p.j1, s), (p.j2, s)
        s1, s2 = sup.get(k1, g1), sup.get(k2, g2)
        if n.get(p.j1, 0) >= minimo and n.get(p.j2, 0) >= minimo and (desde is None or p.fecha >= desde):
            r1 = (1 - w) * g1 + w * s1
            r2 = (1 - w) * g2 + w * s2
            out.append((esperado(r1, r2), p.gana1, p.sets_max, p.s1, p.s2, s, p.fecha, p.retirada, p.tour))
        # actualización (igual que tenis.EloTenis)
        ee = esperado(g1, g2)
        r = 1.0 if p.gana1 else 0.0
        if p.retirada:
            r = 0.5 + (r - 0.5) * 0.5
        m1, m2 = n.get(p.j1, 0), n.get(p.j2, 0)
        gen[p.j1] = g1 + k(m1) * (r - ee)
        gen[p.j2] = g2 + k(m2) * ((1 - r) - (1 - ee))
        n[p.j1], n[p.j2] = m1 + 1, m2 + 1
        sa, sb = sup.get(k1, 1500), sup.get(k2, 1500)
        es = esperado(sa, sb)
        q1, q2 = ns.get(k1, 0), ns.get(k2, 0)
        sup[k1] = sa + k(q1) * (r - es)
        sup[k2] = sb + k(q2) * ((1 - r) - (1 - es))
        ns[k1], ns[k2] = q1 + 1, q2 + 1
    return out


def logloss(pred):
    t = 0
    for p, g, *_ in pred:
        q = min(max(p if g else 1 - p, 1e-6), 1)
        t -= math.log(q)
    return t / max(1, len(pred))


def brier(pred):
    return sum((p - (1 if g else 0)) ** 2 for p, g, *_ in pred) / max(1, len(pred))


def temperatura(pred):
    """Factor que multiplica el logit: <1 = el modelo se pasa de seguro, >1 = se queda corto."""
    mejor, tm = 9e9, 1
    for t in [x / 100 for x in range(50, 161, 2)]:
        ll = 0
        for p, g, *_ in pred:
            z = math.log(p / (1 - p)) * t
            q = 1 / (1 + math.exp(-z))
            ll -= math.log(max(q if g else 1 - q, 1e-9))
        if ll < mejor:
            mejor, tm = ll, t
    return tm


def tabla(pred, f=lambda x: x):
    """Calibración por tramos de la probabilidad del favorito."""
    tramos = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    filas = []
    for lo, hi in tramos:
        xs = []
        for p, g, *_ in pred:
            fav = f(p) if p >= 0.5 else 1 - f(p)
            gana_fav = g if p >= 0.5 else not g
            if lo <= fav < hi:
                xs.append((fav, gana_fav))
        if xs:
            filas.append({"tramo": f"{int(lo*100)}-{int(min(hi,1)*100)}%", "n": len(xs),
                          "prevista": round(sum(x for x, _ in xs) / len(xs), 3),
                          "real": round(sum(1 for _, y in xs if y) / len(xs), 3)})
    return filas


def sets_iid(p_partido):
    s = tenis.p_set_desde_partido(p_partido)
    return s, s * s, s * s * 2 * (1 - s)  # p_set, P(2-0), P(2-1)


def mercados_sets(pred):
    """Bo3 sin abandonos: lo que predice el modelo para los sets frente a lo que pasó."""
    tramos = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    filas = []
    for lo, hi in tramos:
        n = pv20 = r20 = pv3 = r3 = pvmas = rmas = 0
        for p, g, sm, a, b, *_rest in pred:
            ret = _rest[2]
            if sm != 3 or ret or a is None or b is None or max(a, b) != 2:
                continue
            fav_p = p if p >= 0.5 else 1 - p
            if not (lo <= fav_p < hi):
                continue
            fa, fb = (a, b) if p >= 0.5 else (b, a)
            s, p20, p21 = sets_iid(fav_p)
            n += 1
            pv20 += p20
            r20 += fa == 2 and fb == 0
            pv3 += 1 - (1 - s) ** 2 - 0  # el no favorito NO gana 2-0  =  favorito +1.5 sets
            r3 += not (fb == 2 and fa == 0)
            pvmas += 2 * s * (1 - s)        # se juega el tercer set
            rmas += a + b == 3
        if n:
            filas.append({"tramo": f"{int(lo*100)}-{int(min(hi,1)*100)}%", "n": n,
                          "fav 2-0 previsto": round(pv20 / n, 3), "fav 2-0 real": round(r20 / n, 3),
                          "fav +1.5 sets previsto": round(pv3 / n, 3), "fav +1.5 sets real": round(r3 / n, 3),
                          "3 sets previsto": round(pvmas / n, 3), "3 sets real": round(rmas / n, 3)})
    return filas


def sets_con_rho(pred, t, rho):
    """Calibración de los mercados de sets con el modelo encadenado (rho) y la temperatura t."""
    tramos = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    filas, ll, nn = [], 0.0, 0
    acum = {tr: [0, 0, 0, 0, 0, 0, 0] for tr in tramos}
    for p, g, sm, a, b, *_rest in pred:
        if sm != 3 or _rest[2] or a is None or b is None or max(a, b) != 2:
            continue
        z = math.log(p / (1 - p)) * t
        p = 1 / (1 + math.exp(-z))
        s = tenis.p_set_desde_partido(p, 3, rho)
        m = tenis.marcadores_sets(s, 3, rho)
        ll -= math.log(max(m.get((a, b), 1e-9), 1e-9))
        nn += 1
        fav = p >= 0.5
        fp = p if fav else 1 - p
        fa, fb = (a, b) if fav else (b, a)
        mf = m if fav else {(y, x): v for (x, y), v in m.items()}
        for tr in tramos:
            if tr[0] <= fp < tr[1]:
                c = acum[tr]
                c[0] += 1
                c[1] += mf[(2, 0)]; c[2] += fa == 2 and fb == 0
                c[3] += 1 - mf[(0, 2)]; c[4] += not (fa == 0 and fb == 2)
                c[5] += mf[(2, 1)] + mf[(1, 2)]; c[6] += a + b == 3
    for tr, c in acum.items():
        if c[0]:
            n = c[0]
            filas.append({"tramo": f"{int(tr[0]*100)}-{int(min(tr[1],1)*100)}%", "n": n,
                          "fav 2-0": [round(c[1]/n, 3), round(c[2]/n, 3)], "fav +1.5 sets": [round(c[3]/n, 3), round(c[4]/n, 3)],
                          "3 sets": [round(c[5]/n, 3), round(c[6]/n, 3)]})
    return ll / max(1, nn), filas


def final():
    """Comprueba los parámetros que usa la app (tenis.PARAMS y tenis.RHO_SETS) y ajusta rho."""
    hoy = date.today()
    out = {}
    for tour in tenis.TOURS:
        partidos = [p for p in tenis.historico(tour, hoy) if p.gana1 is not None]
        corte = partidos[len(partidos) // 3].fecha
        pr = tenis.PARAMS[tour]
        pred = recorrer(partidos, pr["a"], pr["e"], pr["w_sup"], desde=corte)
        t = pr["t"]
        cal = lambda p: 1 / (1 + math.exp(-math.log(p / (1 - p)) * t))  # noqa: E731
        predc = [(cal(p),) + tuple(x) for p, *x in pred]
        rhos = {r: round(sets_con_rho(pred, t, r)[0], 4) for r in [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4]}
        mejor_rho = min(rhos, key=rhos.get)
        out[tour] = {"params": pr, "temperatura_optima": temperatura(pred), "logloss": round(logloss(predc), 4),
                     "tabla": tabla(predc), "rho_logloss": rhos, "rho_mejor": mejor_rho,
                     "sets_app (previsto, real)": sets_con_rho(pred, t, tenis.RHO_SETS)[1],
                     "sets_mejor_rho": sets_con_rho(pred, t, mejor_rho)[1]}
    print(json.dumps(out, indent=1, ensure_ascii=False))


def main():
    hoy = date.today()
    salida = {}
    for tour in tenis.TOURS:
        partidos = [p for p in tenis.historico(tour, hoy) if p.gana1 is not None]
        print(f"{tour}: {len(partidos)} partidos")
        if len(partidos) < 300:
            continue
        corte = partidos[len(partidos) // 3].fecha  # el primer tercio solo sirve para arrancar el Elo
        base = recorrer(partidos, desde=corte)
        res = {"partidos": len(partidos), "evaluados": len(base), "desde": corte.isoformat(),
               "actual": {"logloss": round(logloss(base), 4), "brier": round(brier(base), 4),
                          "acierto": round(sum(1 for p, g, *_ in base if (p >= 0.5) == bool(g)) / len(base), 3),
                          "temperatura": temperatura(base), "tabla": tabla(base), "sets": mercados_sets(base)}}
        # búsqueda de parámetros
        mejores = []
        for a, e, w, mn in itertools.product([150, 200, 250, 300, 400], [0.3, 0.4, 0.5], [0, 0.25, 0.5, 0.75], [8]):
            pr = recorrer(partidos, a, e, w, mn, desde=corte)
            mejores.append((logloss(pr), a, e, w, len(pr)))
        mejores.sort()
        res["mejores"] = [{"logloss": round(x[0], 4), "a": x[1], "e": x[2], "w_sup": x[3], "n": x[4]} for x in mejores[:6]]
        _, a, e, w, _ = mejores[0]
        best = recorrer(partidos, a, e, w, desde=corte)
        t = temperatura(best)
        res["mejor"] = {"a": a, "e": e, "w_sup": w, "logloss": round(logloss(best), 4), "brier": round(brier(best), 4),
                        "temperatura": t, "tabla": tabla(best), "sets": mercados_sets(best)}
        cal = lambda p: 1 / (1 + math.exp(-math.log(p / (1 - p)) * t))  # noqa: E731
        res["mejor"]["tabla_calibrada"] = tabla(best, cal)
        # ¿pierde algo el umbral de 8 partidos? prueba 5, 12 y 20
        res["minimo"] = {mn: round(logloss(recorrer(partidos, a, e, w, mn, desde=corte)), 4) for mn in (5, 8, 12, 20)}
        salida[tour] = res
    print(json.dumps(salida, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    final() if "--final" in sys.argv else main()
