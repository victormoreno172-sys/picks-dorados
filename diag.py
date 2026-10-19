import json, tenis, rankings
from datetime import date
M = [("WTA","Paula Badosa","Antonia Ruzic",.720),("WTA","Diana Shnaider","Yulia Putintseva",.734),("WTA","Belinda Bencic","Jelena Ostapenko",.570),
     ("WTA","Jasmine Paolini","Anhelina Kalinina",.654),("WTA","Ekaterina Alexandrova","Guo Hanyu",.771),("WTA","Sara Bejlek","Alycia Parks",.818),
     ("ATP","Stefanos Tsitsipas","Aleksandar Kovacevic",.776),("ATP","Roman Safiullin","Sho Shimabukuro",.834),("WTA","Moyuka Uchijima","Ena Shibahara",.592),
     ("ATP","Karen Khachanov","Rei Sakamoto",.679)]
out = {}
hoy = date.today()
E, ID = {}, {}
for tour in ("ATP", "WTA"):
    hist = tenis.historico(tour, hoy)
    for h in hist + tenis.proximos(tour, hoy, 3):
        ID[h.n1] = h.j1; ID[h.n2] = h.j2
    E[tour] = tenis.EloTenis(tour).ajustar(hist)
res = []
for npri, lam in ((None, 0), (25, 0), (25, .2), (25, .35), (25, .5), (10, .35), (50, .35)):
    errs = []
    for tour, a, b, mk in M:
        e = E[tour]
        if npri is None:
            e.prior = {}
        else:
            e.poner_ranking({f"{tour}-{i}": r for i, r in rankings.tenis_ids(tour.lower()).items()}); e.N_PRIOR = npri; e.LAMBDA0 = lam
        ia, ib = ID.get(a, a), ID.get(b, b)
        p = e.p_partido(ia, ib, "dura")
        errs.append((a, round(p, 3), mk, e.n.get(ia, 0), e.n.get(ib, 0), ia in e.prior, ib in e.prior))
    mae = sum(abs(x[1] - x[2]) for x in errs) / len(errs)
    res.append({"N_PRIOR": npri, "lam": lam, "mae": round(mae, 3), "recta": getattr(E["ATP"], "_recta", None), "detalle": errs})
out["res"] = res
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False)
