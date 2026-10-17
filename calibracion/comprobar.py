import sys; sys.path.insert(0,"/home/claude/repo-picks")
import analisis, numpy as np
from scipy.stats import poisson
from modelo import mercados
P={
"RM-Sevilla":({"Gana local (1)":1.15,"Empate (X)":7.0,"Gana visitante (2)":10.5,"Más de 2.5 goles":1.42,"Menos de 2.5 goles":2.80},
 {"Local o empate (1X)":1.07,"No hay empate (12)":1.13,"Visitante o empate (X2)":4.10,"Ambos marcan: Sí":1.72,"Ambos marcan: No":1.74,
"Más de 1.5 goles":1.13,"Menos de 1.5 goles":6.0,"Más de 3.5 goles":2.05,"Menos de 3.5 goles":1.76,"Más de 4.5 goles":3.35,"Menos de 4.5 goles":1.32,
"Local marca":1.04,"Visitante marca":1.74}),
"Leeds-United":({"Gana local (1)":2.25,"Empate (X)":3.5,"Gana visitante (2)":2.7,"Más de 2.5 goles":1.66,"Menos de 2.5 goles":2.20},
 {"Local o empate (1X)":1.44,"No hay empate (12)":1.32,"Visitante o empate (X2)":1.58,"Ambos marcan: Sí":1.56,"Ambos marcan: No":2.40,
"Más de 1.5 goles":1.20,"Menos de 1.5 goles":4.50,"Más de 3.5 goles":2.55,"Menos de 3.5 goles":1.50,
"Más de 0.5 goles":1.04,"Menos de 0.5 goles":13.5,"Local marca":1.19,"Visitante marca":1.24}),
"Racing-Independiente":({"Gana local (1)":2.0,"Empate (X)":3.0,"Gana visitante (2)":3.35},
 {"Local o empate (1X)":1.27,"No hay empate (12)":1.35,"Visitante o empate (X2)":1.68,"Ambos marcan: Sí":1.96,"Ambos marcan: No":1.76,
"Más de 0.5 goles":1.07,"Menos de 0.5 goles":7.25,"Más de 1.5 goles":1.39,"Menos de 1.5 goles":2.80,"Más de 2.5 goles":2.25,"Menos de 2.5 goles":1.58,"Más de 3.5 goles":4.10,"Menos de 3.5 goles":1.20,
"Local marca":1.27,"Visitante marca":1.50}),
"Belgrano-River":({"Gana local (1)":3.15,"Empate (X)":2.95,"Gana visitante (2)":2.10},
 {"Local o empate (1X)":1.62,"No hay empate (12)":1.36,"Visitante o empate (X2)":1.30,"Ambos marcan: Sí":2.15,"Ambos marcan: No":1.64,
"Más de 0.5 goles":1.09,"Menos de 0.5 goles":6.5,"Más de 1.5 goles":1.49,"Menos de 1.5 goles":2.45,"Más de 2.5 goles":2.50,"Menos de 2.5 goles":1.47,"Más de 3.5 goles":4.90,"Menos de 3.5 goles":1.15,
"Local marca":1.56,"Visitante marca":1.34}),
"Forest-Arsenal":({"Gana local (1)":5.5,"Empate (X)":3.75,"Gana visitante (2)":1.54,"Más de 2.5 goles":1.92,"Menos de 2.5 goles":1.86},
 {"Local o empate (1X)":2.30,"No hay empate (12)":1.28,"Visitante o empate (X2)":1.15,"Ambos marcan: Sí":1.96,"Ambos marcan: No":1.82,
"Más de 0.5 goles":1.06,"Menos de 0.5 goles":9.5,"Más de 1.5 goles":1.30,"Menos de 1.5 goles":3.55,"Más de 3.5 goles":3.25,"Menos de 3.5 goles":1.34,
"Local marca":1.66,"Visitante marca":1.14}),
}
TOT={'Racing-Independiente':2.245,'Belgrano-River':1.869,'Leeds-United':2.728,'Forest-Arsenal':2.269,'RM-Sevilla':3.37}
def run(rho=0.0, verbose=True):
    errs=[]
    for n,(c,w) in P.items():
        l,m,mg=analisis.goles_del_mercado(c, TOT.get(n))
        M=analisis.tabla_mercado(l,m); pm=mercados(M)
        picks=[analisis.Pick(k,pm[k]) for k in w]; analisis.estimar_cuotas(picks,pm,mg)
        if verbose: print(n, "λ %.2f μ %.2f margen %.3f"%(l,m,mg))
        for p in picks:
            if p.cuota is None: continue
            e=p.cuota/w[p.mercado]-1; errs.append(abs(e))
            if verbose: print(f"   {p.mercado:26s} winamax {w[p.mercado]:5.2f} app {p.cuota:5.2f} {e:+.1%}")
    print("error medio %.1f%%"%(100*np.mean(errs)))
run()

import sys
if "--grid" not in sys.argv: sys.exit()
import itertools
best=None
for fb,fm,fd,ft in itertools.product([1,1.3,1.6,2,2.5],[0.8,1,1.2,1.5],[0.5,0.67,0.8,1],[0.8,1,1.2,1.4]):
    analisis.FACTOR_MARGEN=(("Ambos marcan",fb),(" marca",fm),("o empate",fd),("No hay empate",fd),("goles",ft))
    errs=[]
    for n,(c,w) in P.items():
        l,m,mg=analisis.goles_del_mercado(c, TOT.get(n))
        M=analisis.tabla_mercado(l,m); pm=mercados(M)
        picks=[analisis.Pick(k,pm[k]) for k in w]; analisis.estimar_cuotas(picks,pm,mg)
        errs+=[abs(np.log(p.cuota/w[p.mercado])) for p in picks if p.cuota]
    e=np.mean(errs)
    if best is None or e<best[0]: best=(e,fb,fm,fd,ft)
print("mejor", best)
