"""Pruebas sin internet del baloncesto:  python tests_baloncesto.py"""
from datetime import date, timedelta

import numpy as np

import baloncesto as b

ESPN = {"events": [{
    "date": "2026-10-21T23:00Z", "season": {"type": 2},
    "competitions": [{
        "status": {"type": {"completed": False}},
        "competitors": [
            {"homeAway": "home", "score": "0", "team": {"abbreviation": "ORL", "displayName": "Orlando Magic"}},
            {"homeAway": "away", "score": "0", "team": {"abbreviation": "GS", "displayName": "Golden State Warriors"}}],
        "odds": [{"details": "GS -4.5", "overUnder": 228.5}]}]},
    {"date": "2026-10-05T23:00Z", "season": {"type": 1}, "competitions": [{"competitors": []}]}]}

TSDB = {"idEvent": "1", "idHomeTeam": "134", "idAwayTeam": "135", "strHomeTeam": "Valencia Basket",
        "strAwayTeam": "Olympiacos BC", "intHomeScore": "97", "intAwayScore": "102",
        "strTimestamp": "2026-10-13T18:30:00", "strStatus": "FT"}


def test_parseo():
    j = b._parse_espn(ESPN)
    assert len(j) == 1  # la pretemporada se descarta
    j = j[0]
    assert j.local_id == "NBA-ORL" and j.visit_id == "NBA-GSW" and not j.jugado
    assert j.spread_local == 4.5 and j.total_casa == 228.5  # el visitante es favorito
    assert j.hora == "01:00" and j.fecha == date(2026, 10, 22)  # hora de Madrid
    k = b._evento_a_juego("EL", TSDB)
    assert k.jugado and k.pl == 97 and k.local_id == "T134" and k.hora == "20:30"


def liga_simulada(seed=0):
    rng = np.random.default_rng(seed)
    eq = [f"E{i}" for i in range(16)]
    att = dict(zip(eq, rng.normal(0, 5, 16)))
    dfn = dict(zip(eq, rng.normal(0, 4, 16)))
    juegos, d = [], date(2025, 10, 1)
    for _ in range(3):
        for h in eq:
            for a in eq:
                if h != a:
                    pl = 82 + att[h] + dfn[a] + 3 + rng.normal(0, 9)
                    pv = 82 + att[a] + dfn[h] + rng.normal(0, 9)
                    juegos.append(b.Juego("ACB", d, "", h, a, h, a, int(round(pl)), int(round(pv))))
            d += timedelta(days=2)
    return juegos, att, dfn


def test_modelo():
    juegos, att, dfn = liga_simulada()
    m = b.ModeloBaloncesto(xi=0.0).ajustar(juegos, hasta=date(2027, 1, 1))
    est = np.array([m.ataque[e] for e in att])
    assert np.corrcoef(est, list(att.values()))[0, 1] > 0.9
    assert 2 < m.local["ACB"] < 4.5, m.local
    assert 11 < m.sd_margen < 15.5, m.sd_margen  # ≈ 9·√2 · 1.05
    j = b.Juego("ACB", date(2027, 1, 2), "20:00", "E0", "E1", "E0", "E1")
    a = b.analizar_juego(j, m)
    probs = {p.mercado: p.prob for p in a.picks}
    assert abs(probs["Gana local"] + probs["Gana visitante"] - 1) < 1e-9
    for k, v in probs.items():
        if k.startswith("Más de"):
            assert abs(v + probs[k.replace("Más de", "Menos de")] - 1) < 1e-9
    assert 150 < a.goles_local + a.goles_visitante < 185


def test_lineas_casa():
    ps = b.mercados_baloncesto(margen=-6, total=230, sd_m=13, sd_t=18, spread_casa=4.5, total_casa=228.5)
    d = {p.mercado: p for p in ps}
    assert d["Hándicap visitante -4.5"].cuota == b.CUOTA_ESTANDAR
    assert d["Hándicap visitante -4.5"].prob > 0.5   # esperamos ganar de 6, la casa da 4.5
    assert d["Más de 228.5 puntos"].prob > 0.5
    assert len([p for p in ps if p.mercado == "Más de 228.5 puntos"]) == 1


if __name__ == "__main__":
    for t in (test_parseo, test_modelo, test_lineas_casa):
        t()
        print(f"OK  {t.__name__}")
