import io, json, contextlib, sys, math
sys.path.insert(0, "calibracion")
import backtest_tenis as bt, tenis
from datetime import date
out = {}
hoy = date.today()
for tour in tenis.TOURS:
    partidos = [p for p in tenis.historico(tour, hoy) if p.gana1 is not None]
    corte = partidos[len(partidos) // 3].fecha
    pr = tenis.PARAMS[tour]
    pred = bt.recorrer(partidos, pr["a"], pr["e"], pr["w_sup"], desde=corte)
    # Mercado "+1.5 sets" de cada jugador (no perder 0-2), por tramos de probabilidad prevista (como lo usa la app)
    tramos = {}
    for p, g, sm, a, b, *rest in pred:
        if sm != 3 or rest[2] or a is None or b is None or max(a, b) != 2:
            continue
        z = math.log(p / (1 - p)) * pr["t"]; q = 1 / (1 + math.exp(-z))
        s = tenis.p_set_desde_partido(q, 3, tenis.RHO_SETS)
        m = tenis.marcadores_sets(s, 3, tenis.RHO_SETS)
        for lado, prob, real in ((1, 1 - m[(0, 2)], not (a == 0 and b == 2)), (2, 1 - m[(2, 0)], not (a == 2 and b == 0))):
            if prob < 0.7:
                continue
            k = f"{int(prob * 20) * 5}-{int(prob * 20) * 5 + 5}%"
            t = tramos.setdefault(k, [0, 0.0, 0])
            t[0] += 1; t[1] += prob; t[2] += real
    out[tour] = {k: {"n": v[0], "previsto": round(v[1] / v[0], 3), "real": round(v[2] / v[0], 3)} for k, v in sorted(tramos.items())}
json.dump(out, open("resultado.json", "w"), indent=1)
