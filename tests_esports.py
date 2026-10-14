"""Pruebas sin internet de esports:  python tests_esports.py"""
from datetime import date, timedelta

import numpy as np

import esports as es


def test_marcadores():
    for bo in (1, 3, 5):
        for p in (0.3, 0.5, 0.72):
            m = es.marcadores(p, bo)
            assert abs(sum(m.values()) - 1) < 1e-12
    m = es.marcadores(0.6, 3)
    assert abs(m[(2, 0)] - 0.36) < 1e-12 and abs(m[(2, 1)] - 2 * 0.36 * 0.4) < 1e-12
    picks, marcador, pm = es.mercados_serie("Vitality", "G2", 0.6, 3)
    d = {k.mercado: k.prob for k in picks}
    assert abs(d["Gana Vitality"] - 0.648) < 1e-12
    assert abs(d["Vitality -1.5 mapas"] - 0.36) < 1e-12 and abs(d["G2 +1.5 mapas"] - 0.64) < 1e-12
    assert abs(d["Más de 2.5 mapas"] - 0.48) < 1e-12
    assert marcador == (2, 1) or marcador == (2, 0)
    picks5, _, _ = es.mercados_serie("A", "B", 0.55, 5)
    assert any(k.mercado == "Más de 4.5 mapas" for k in picks5)
    picks1, _, _ = es.mercados_serie("A", "B", 0.55, 1)
    assert len(picks1) == 2


def test_modelo():
    rng = np.random.default_rng(0)
    fuerza = {f"CS2-{i}": rng.normal(0, 0.8) for i in range(20)}
    series, d = [], date(2026, 1, 1)
    for k in range(1500):
        a, b = rng.choice(list(fuerza), 2, replace=False)
        p = 1 / (1 + np.exp(-(fuerza[a] - fuerza[b])))
        g1 = g2 = 0
        while g1 < 2 and g2 < 2:
            if rng.random() < p: g1 += 1
            else: g2 += 1
        series.append(es.Serie("CS2", k, d + timedelta(days=k // 8), "20:00", "IEM", "a", 3, a, b, a, b, g1, g2))
    m = es.ModeloMapas(xi=0).ajustar(series, date(2027, 1, 1))
    est = np.array([m.fuerza[e] for e in fuerza])
    assert np.corrcoef(est, list(fuerza.values()))[0, 1] > 0.9
    s = es.Serie("CS2", 1, date(2027, 1, 2), "18:00", "IEM Chicago", "s", 3, "CS2-0", "CS2-1", "Equipo A", "Equipo B")
    a = es.analizar_serie(s, m)
    assert a.partido.deporte == "e" and "IEM Chicago" in a.partido.liga and "Bo3" in a.partido.liga


def test_a_serie():
    m = {"id": 9, "start_date": "2026-10-15T16:00:00.000+00:00", "status": "upcoming", "tier": "s", "bo_type": 3,
         "team1_id": 1, "team2_id": 2, "team1_score": 0, "team2_score": 0,
         "team1": {"name": "Vitality"}, "team2": {"name": "NAVI"}, "tournament": {"name": " IEM Chicago 2026"}}
    s = es._a_serie("CS2", m)
    assert s.hora == "18:00" and s.torneo == "IEM Chicago 2026" and s.m1 is None and s.eq1 == "CS2-1"


def test_cuotas():
    assert abs(es._p_mapa_para(0.648, 3) - 0.6) < 1e-6
    s = es.Serie("CS2", 1, date(2027, 1, 2), "18:00", "IEM", "s", 3, "x", "y", "Aurora", "NIP",
                 cuotas={"path": "https://thunderpick.io/m/1", "team_1": {"coeff": 1.25}, "team_2": {"coeff": 3.5}})
    assert es._cuotas_ganador(s) == (1.25, 3.5, "Thunderpick")


if __name__ == "__main__":
    for t in (test_marcadores, test_modelo, test_a_serie, test_cuotas):
        t()
        print(f"OK  {t.__name__}")
