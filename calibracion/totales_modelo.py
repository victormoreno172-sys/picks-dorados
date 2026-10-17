"""Goles esperados del modelo propio para los partidos de calibración (se ejecuta en GitHub)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date
import espn_futbol, datos
from modelo import ModeloDixonColes
hoy = date.today()
for liga, partidos in (("ARG", [("Racing Club", "Independiente"), ("Belgrano (Córdoba)", "River Plate")]),
                       ("MLS", [("FC Cincinnati", "Columbus Crew")])):
    h = espn_futbol.historico(liga, hoy)
    m = ModeloDixonColes().ajustar(h, hasta=hoy)
    tot = [p.goles_local + p.goles_visitante for p in h if (hoy - p.fecha).days < 365]
    print(liga, "media de goles último año %.2f" % (sum(tot) / len(tot)), "rho", getattr(m, "rho", None))
    for l, v in partidos:
        print("  ", l, v, m.goles_esperados(l, v) if m.conoce(l) and m.conoce(v) else "desconocido")
for liga, partidos in (("E0", [("Leeds", "Man United"), ("Nott'm Forest", "Arsenal")]), ("SP1", [("Real Madrid", "Sevilla")])):
    h = datos.historico(liga, hoy)
    m = ModeloDixonColes().ajustar(h, hasta=hoy)
    for l, v in partidos:
        print("  ", liga, l, v, m.goles_esperados(l, v))
