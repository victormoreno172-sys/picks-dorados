"""Pruebas sin internet del tenis:  python tests_tenis.py"""
from datetime import date, timedelta

import numpy as np

import tenis as t

ESPN = {"events": [{"name": "Rolex Shanghai Masters", "groupings": [
    {"grouping": {"displayName": "Men's Singles"}, "competitions": [
        {"id": "1", "date": "2026-10-05T04:05Z", "status": {"type": {"completed": True, "name": "STATUS_FINAL"}},
         "round": {"displayName": "R32"}, "format": {"regulation": {"periods": 3}},
         "competitors": [{"winner": True, "athlete": {"id": "10", "displayName": "Carlos Alcaraz"},
                          "linescores": [{"value": 6}, {"value": 3}, {"value": 7}]},
                         {"winner": False, "athlete": {"id": "11", "displayName": "Jannik Sinner"},
                          "linescores": [{"value": 4}, {"value": 6}, {"value": 6}]}]},
        {"id": "2", "date": "2026-10-16T08:00Z", "status": {"type": {"completed": False, "name": "STATUS_SCHEDULED"}},
         "round": {"displayName": "QF"}, "format": {"regulation": {"periods": 3}},
         "competitors": [{"athlete": {"id": "10", "displayName": "Carlos Alcaraz"}},
                         {"athlete": {"id": "12", "displayName": "Novak Djokovic"}}]}]},
    {"grouping": {"displayName": "Men's Doubles"}, "competitions": []}]}]}


def test_parseo():
    ps = t._parsear("ATP", ESPN)
    assert len(ps) == 2
    a, b = ps
    assert a.gana1 is True and (a.s1, a.s2) == (2, 1) and a.j1 == "ATP-10" and a.hora == "06:05"
    assert b.gana1 is None and b.n2 == "Novak Djokovic"


def test_superficie():
    assert t.superficie("Mutua Madrid Open", date(2026, 5, 1)) == "tierra"
    assert t.superficie("Wimbledon", date(2026, 7, 1)) == "hierba"
    assert t.superficie("Rolex Shanghai Masters", date(2026, 10, 5)) == "dura"


def test_set_y_mercados():
    s = t.p_set_desde_partido(0.648, 3, 0)  # sets independientes: 0.6 por set -> 0.648 el partido
    assert abs(s - 0.6) < 1e-6
    # con sets encadenados se juegan menos terceros sets
    m = t.marcadores_sets(t.p_set_desde_partido(0.648), 3)
    assert m[(2, 1)] + m[(1, 2)] < 0.6 * 0.4 * 2
    picks, (a, b), pm, s = t.mercados_tenis("Alcaraz", "Sinner", 0.648, 3)
    d = {k.mercado: k.prob for k in picks}
    assert abs(d["Gana Alcaraz"] - 0.648) < 1e-6 and "Alcaraz -1.5 sets" in d and "Más de 2.5 sets" in d
    picks5, *_ = t.mercados_tenis("A", "B", 0.7, 5)
    assert any(k.mercado == "Más de 3.5 sets" for k in picks5)


def test_elo():
    rng = np.random.default_rng(1)
    nivel = {f"ATP-{i}": 1500 + 60 * i for i in range(12)}
    ps, d = [], date(2025, 10, 1)
    for k in range(2500):
        x, y = rng.choice(list(nivel), 2, replace=False)
        p = 1 / (1 + 10 ** ((nivel[y] - nivel[x]) / 400))
        g = rng.random() < p
        ps.append(t.Partido("ATP", str(k), d + timedelta(days=k // 10), "", "Shanghai", "", 3, x, y, x, y, g, 2 if g else 0, 0 if g else 2))
    elo = t.EloTenis().ajustar(ps)
    est = [elo.general[j] for j in nivel]
    assert np.corrcoef(est, list(nivel.values()))[0, 1] > 0.9
    assert elo.p_partido("ATP-11", "ATP-0", "dura") > 0.8


if __name__ == "__main__":
    for f in (test_parseo, test_superficie, test_set_y_mercados, test_elo):
        f()
        print(f"OK  {f.__name__}")
