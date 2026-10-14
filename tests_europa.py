"""Pruebas sin internet del módulo europeo:  python tests_europa.py"""
from datetime import date, timedelta

import numpy as np

import europa

TEXTO_OF = """= UEFA Champions League 2025/26

▪ League, Matchday 1
  Tue Sep 16 2025
    18:45  Athletic Club (ESP)     v Arsenal FC (ENG)         0-2 (0-0)
    21:00  PSV (NED)               v Union Saint-Gilloise (BEL) 1-3 (0-1)
  Wed Sep 17 2025
    21:00  FC Bayern München (GER) v Chelsea FC (ENG)        3-1 (2-1)
    21:00  Crvena zvezda (SRB)     v Qarabağ FK (AZE)          2-2
▪ Final
  Sat May 30 2026
    18:00  Real Madrid CF (ESP)    v Paris Saint-Germain (FRA) 1-1 a.e.t. (1-1, 0-0) 4-3 pen.
"""

EQUIPOS = {
    "ESP": {"Ath Bilbao", "Real Madrid", "Ath Madrid", "Betis", "Celta"},
    "ENG": {"Arsenal", "Chelsea", "Man City", "Man United", "Aston Villa", "Brighton"},
    "NED": {"PSV Eindhoven", "Feyenoord", "Ajax"},
    "BEL": {"St. Gilloise", "Club Brugge", "Anderlecht"},
    "GER": {"Bayern Munich", "Dortmund"},
    "FRA": {"Paris SG", "Lyon", "Marseille"},
    "ITA": {"Inter", "Milan", "Como"},
    "TUR": {"Fenerbahce", "Galatasaray"},
    "DEN": {"Nordsjaelland", "FC Copenhagen"},
}


def test_parseo():
    p = europa.parsear_openfootball(TEXTO_OF, 2025)
    assert len(p) == 5, p
    assert p[0] == (date(2025, 9, 16), "Athletic Club", "ESP", "Arsenal FC", "ENG", 0, 2)
    assert p[3][1] == "Crvena zvezda" and p[3][2] == "SRB"
    assert p[4][0] == date(2026, 5, 30) and p[4][5:] == (1, 1)


def test_emparejar():
    e = europa.Emparejador(EQUIPOS)
    casos = {
        ("Athletic Club", "ESP"): "Ath Bilbao", ("Arsenal FC", "ENG"): "Arsenal",
        ("PSV", "NED"): "PSV Eindhoven", ("Union Saint-Gilloise", "BEL"): "St. Gilloise",
        ("FC Bayern München", "GER"): "Bayern Munich", ("Chelsea FC", "ENG"): "Chelsea",
        ("Real Madrid CF", "ESP"): "Real Madrid", ("Paris Saint-Germain", "FRA"): "Paris SG",
        # TheSportsDB (sin país)
        ("Manchester City", None): "Man City", ("Paris Saint-Germain", None): "Paris SG",
        ("Fenerbahçe", None): "Fenerbahce", ("Como", None): "Como", ("Feyenoord", None): "Feyenoord",
        ("Brighton and Hove Albion", None): "Brighton", ("FC Nordsjælland", None): "Nordsjaelland",
        ("Aston Villa", None): "Aston Villa", ("Inter Turku", None): "~inter turku",
    }
    for (n, p), esperado in casos.items():
        assert e(n, p) == esperado, (n, p, e(n, p))
    # mismo equipo sin liga, escrito por dos fuentes distintas -> mismo identificador
    assert e("Crvena zvezda", "SRB") == e("Crvena Zvezda") == "~crvena zvezda"
    assert e("Qarabağ FK", "AZE") == e("Qarabağ")


def test_modelo_conecta_ligas():
    """Dos ligas con niveles distintos que solo se conectan por partidos europeos."""
    rng = np.random.default_rng(0)
    nivel = {"A": 0.35, "B": -0.35}
    equipos = {liga: [f"{liga}{i}" for i in range(12)] for liga in nivel}
    fuerza = {e: nivel[l] + rng.normal(0, 0.15) for l, es in equipos.items() for e in es}
    partidos, d = [], date(2024, 8, 1)
    def jugar(h, a, eu, liga=""):
        gl = rng.poisson(np.exp(0.1 + fuerza[h] - fuerza[a] * 0.6 + (0.15 if eu else 0.25)))
        gv = rng.poisson(np.exp(0.1 + fuerza[a] - fuerza[h] * 0.6))
        partidos.append(europa.PartidoEu(d, h, a, int(gl), int(gv), eu, liga))
    for _ in range(2):
        for liga, es in equipos.items():
            for h in es:
                for a in es:
                    if h != a:
                        jugar(h, a, False, liga)
        for _ in range(60):
            jugar(rng.choice(equipos["A"]), rng.choice(equipos["B"]), True)
            jugar(rng.choice(equipos["B"]), rng.choice(equipos["A"]), True)
        d += timedelta(days=200)
    m = europa.ModeloEuropeo().ajustar(partidos, hasta=d)
    media = {l: np.mean([m.att[e] - m.dfn[e] for e in es]) for l, es in equipos.items()}
    assert media["A"] - media["B"] > 0.5, media  # el modelo ve que la liga A es mejor
    assert m.nivel_liga["A"] - m.nivel_liga["B"] > 0.4, m.nivel_liga
    lam, mu = m.goles_esperados("A0", "B0")
    assert lam > mu
    t = m.tabla_marcadores("A0", "B0")
    assert abs(t.sum() - 1) < 1e-9


def test_gradiente():
    from scipy.optimize import check_grad
    rng = np.random.default_rng(1)
    partidos = [europa.PartidoEu(date(2025, 1, 1) + timedelta(days=i), f"T{rng.integers(6)}",
                                 f"T{rng.integers(6, 12)}", int(rng.poisson(1.4)), int(rng.poisson(1.1)),
                                 bool(i % 3 == 0)) for i in range(300)]
    for i, p in enumerate(partidos):
        p.liga = "" if p.europeo else ("L1" if i % 2 else "L2")
    m = europa.ModeloEuropeo()
    # reconstruye la función objetivo igual que ajustar() para comprobar el gradiente
    import types
    capturado = {}
    real_min = europa.minimize
    def espia(f, x0, **kw):
        capturado["f"], capturado["x0"] = f, x0
        return real_min(f, x0, **kw)
    europa.minimize = espia
    try:
        m.ajustar(partidos, hasta=date(2026, 1, 1))
    finally:
        europa.minimize = real_min
    f = capturado["f"]
    x = rng.normal(0, 0.2, len(capturado["x0"]))
    err = check_grad(lambda t: f(t)[0], lambda t: f(t)[1], x)
    assert err < 1e-3 * np.linalg.norm(f(x)[1]), err


if __name__ == "__main__":
    for t in (test_parseo, test_emparejar, test_modelo_conecta_ligas, test_gradiente):
        t()
        print(f"OK  {t.__name__}")
