import json, tenis, rankings
from datetime import date
M = [("WTA","Paula Badosa","Antonia Ruzic",.720),("WTA","Diana Shnaider","Yulia Putintseva",.734),("WTA","Belinda Bencic","Jelena Ostapenko",.570),
     ("WTA","Jasmine Paolini","Anhelina Kalinina",.654),("WTA","Ekaterina Alexandrova","Guo Hanyu",.771),("WTA","Sara Bejlek","Alycia Parks",.818),
     ("ATP","Stefanos Tsitsipas","Aleksandar Kovacevic",.776),("ATP","Roman Safiullin","Sho Shimabukuro",.834),("WTA","Moyuka Uchijima","Ena Shibahara",.592),
     ("ATP","Karen Khachanov","Rei Sakamoto",.679)]
out = {}
hoy = date.today()
E = {}
for tour in ("ATP", "WTA"):
    E[tour] = tenis.EloTenis(tour).ajustar(tenis.historico(tour, hoy))
res = []
for npri, lam in ((None, 0), (25, 0), (25, .2), (25, .35), (25, .5), (10, .35), (50, .35), (25, .65)):
    errs = []
    for tour, a, b, mk in M:
        e = E[tour]
        if npri is None:
            e.prior = {}
        else:
            e.poner_ranking({f"{tour}-{n}": r for n, r in rankings.tenis(tour.lower()).items()}); e.N_PRIOR = npri; e.LAMBDA0 = lam
        p = e.p_partido(f"{tour}-{a}", f"{tour}-{b}", "dura")
        errs.append((a.split()[-1], round(p, 3), mk))
    mae = sum(abs(x[1] - x[2]) for x in errs) / len(errs)
    res.append({"N": npri, "lam": lam, "mae": round(mae, 3), "recta": getattr(E["ATP"], "_recta", None), "d": errs})
json.dump({"res": res}, open("resultado.json", "w"), indent=1, ensure_ascii=False)
