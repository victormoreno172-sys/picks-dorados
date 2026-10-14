"""Pruebas sin internet del historial y las cuotas:  python tests_historial.py"""
import os
import tempfile
from datetime import date, timedelta

import config
import cuotas
import historial
from analisis import Analisis, Pick
from datos import PartidoProximo


def test_acierta():
    a = historial.acierta
    assert a("Gana local (1)", 2, 1) and not a("Gana local (1)", 1, 1)
    assert a("Local o empate (1X)", 1, 1) and a("Más de 2.5 goles", 2, 1) and not a("Más de 2.5 goles", 1, 1)
    assert a("Menos de 160.5 puntos", 80, 79) and not a("Menos de 160.5 puntos", 81, 80)
    assert a("Hándicap local -4.5", 90, 85) and not a("Hándicap local -4.5", 90, 86)
    assert a("Hándicap visitante +12.5", 100, 88) and not a("Hándicap visitante +12.5", 100, 87)
    assert a("Ambos marcan: Sí", 1, 1) and a("Gana visitante", 70, 80)
    assert a("Algo raro", 1, 1) is None


def test_ciclo():
    historial.RUTA = os.path.join(tempfile.mkdtemp(), "h.json")
    historial.RESULTADOS.clear()
    d = date(2026, 10, 14)
    p = PartidoProximo("SP1", d, "21:00", "Betis", "Sevilla", casa="Winamax FR")
    a = Analisis(p, 1.5, 1.0, "1-0", 0.12, [Pick("Gana local (1)", 0.8, 1.45, 0.66),
                                            Pick("Más de 2.5 goles", 0.4, 2.1, 0.45),
                                            Pick("Local marca", 0.85)])
    r = historial.actualizar({d: [a]}, d)
    assert r["pendientes"] == 1 and r["periodos"]["7d"]["dorados"]["n"] == 0
    historial.anotar(d, "Betis", "Sevilla", 2, 0)
    r = historial.actualizar({}, date(2026, 10, 15))
    dor = r["periodos"]["7d"]["dorados"]
    assert dor["n"] == 2 and dor["ok"] == 2, dor   # 1 y "local marca"
    assert r["con_cuota"] == [["2026-10-14", "f", 0.8, 1.45, 1]], r["con_cuota"]
    assert abs(dor["roi"] - 0.45) < 1e-9
    assert r["ultimos"][0]["m"] == "Local marca" and r["ultimos"][0]["ok"]


EV = {"id": "x", "commence_time": "2026-10-18T19:00:00Z", "home_team": "Real Betis", "away_team": "Sevilla",
      "bookmakers": [{"key": "winamax_fr", "markets": [
          {"key": "h2h", "outcomes": [{"name": "Real Betis", "price": 2.1}, {"name": "Draw", "price": 3.3},
                                      {"name": "Sevilla", "price": 3.6}]},
          {"key": "totals", "outcomes": [{"name": "Over", "price": 1.9, "point": 2.5},
                                         {"name": "Under", "price": 1.9, "point": 2.5}]}]}]}
EVB = {"id": "y", "commence_time": "2026-10-21T23:30:00Z", "home_team": "Orlando Magic",
       "away_team": "Atlanta Hawks", "bookmakers": [{"key": "winamax_de", "markets": [
           {"key": "spreads", "outcomes": [{"name": "Orlando Magic", "price": 1.87, "point": -2.5},
                                           {"name": "Atlanta Hawks", "price": 1.93, "point": 2.5}]},
           {"key": "totals", "outcomes": [{"name": "Over", "price": 1.9, "point": 228.5},
                                          {"name": "Under", "price": 1.9, "point": 228.5}]}]}]}


def test_cuotas():
    e = cuotas._traducir(EV, "SP1")
    assert e.casa == "Winamax FR" and e.cuotas["Gana local (1)"] == 2.1 and e.cuotas["Empate (X)"] == 3.3
    assert e.cuotas["Más de 2.5 goles"] == 1.9 and e.fecha == date(2026, 10, 18)
    b = cuotas._traducir(EVB, "NBA")
    assert b.cuotas["Hándicap local -2.5"] == 1.87 and b.cuotas["Hándicap visitante +2.5"] == 1.93
    assert b.spread_local == -2.5 and b.total == 228.5 and b.fecha == date(2026, 10, 22)
    c = cuotas.Cuotas([e, b])
    assert c.buscar("SP1", date(2026, 10, 18), "Betis", "Sevilla") is e
    assert c.buscar("SP1", date(2026, 10, 18), "Sevilla", "Betis") is None
    assert c.buscar("NBA", date(2026, 10, 22), "Orlando Magic", "Atlanta Hawks") is b
    assert c.buscar("E0", date(2026, 10, 18), "Betis", "Sevilla") is None


def test_baloncesto_con_cuotas():
    import baloncesto as bb
    assert bb._contrario("Hándicap local -2.5") == "Hándicap visitante +2.5"
    assert bb._contrario("Más de 228.5 puntos") == "Menos de 228.5 puntos"
    from tests_baloncesto import liga_simulada
    juegos, _, _ = liga_simulada()
    m = bb.ModeloBaloncesto(xi=0).ajustar(juegos, hasta=date(2027, 1, 1))
    j = bb.Juego("ACB", date(2027, 1, 2), "20:00", "E0", "E1", "E0", "E1", spread_local=-3.5, total_casa=165.5)
    j.cuotas = {"Hándicap local -3.5": 1.85, "Hándicap visitante +3.5": 1.95, "Más de 165.5 puntos": 1.9,
                "Menos de 165.5 puntos": 1.9, "Gana local": 1.5, "Gana visitante": 2.6}
    j.casa = "Winamax FR"
    a = bb.analizar_juego(j, m)
    d = {p.mercado: p for p in a.picks}
    assert d["Hándicap local -3.5"].cuota == 1.85 and not d["Hándicap local -3.5"].estimada
    assert abs(d["Gana local"].prob_cuota - (1 / 1.5) / (1 / 1.5 + 1 / 2.6)) < 1e-9
    assert a.partido.casa == "Winamax FR"


if __name__ == "__main__":
    for t in (test_acierta, test_ciclo, test_cuotas, test_baloncesto_con_cuotas):
        t()
        print(f"OK  {t.__name__}")


def test_espn_futbol():
    import espn_futbol
    datos = {"events": [
        {"date": "2026-10-18T23:30Z", "competitions": [{"status": {"type": {"completed": False, "name": "STATUS_SCHEDULED"}},
            "competitors": [{"homeAway": "home", "score": "0", "team": {"displayName": "Inter Miami CF"}},
                            {"homeAway": "away", "score": "0", "team": {"displayName": "LA Galaxy"}}],
            "odds": [{"homeTeamOdds": {"moneyLine": -150}, "awayTeamOdds": {"moneyLine": 320}, "drawOdds": {"moneyLine": 290}}]}]},
        {"date": "2026-10-11T00:30Z", "competitions": [{"status": {"type": {"completed": True, "name": "STATUS_FULL_TIME"}},
            "competitors": [{"homeAway": "home", "score": "2", "team": {"displayName": "Seattle Sounders FC"}},
                            {"homeAway": "away", "score": "1", "team": {"displayName": "Portland Timbers"}}]}]}]}
    p = espn_futbol.parsear(datos)
    assert p[0]["fecha"] == date(2026, 10, 19) and p[0]["hora"] == "01:30" and p[0]["gl"] is None
    assert p[0]["cuotas"] == {"Gana local (1)": 1.67, "Gana visitante (2)": 4.2, "Empate (X)": 3.9}
    assert p[1]["gl"] == 2 and p[1]["fecha"] == date(2026, 10, 11)
    assert config.nombre_liga("MLS") == "🇺🇸 MLS"


if __name__ == "__main__":
    test_espn_futbol()
    print("OK  test_espn_futbol")


def test_esquinas():
    import numpy as np
    import esquinas
    rng = np.random.default_rng(0)
    eq = [f"T{i}" for i in range(12)]
    saca = dict(zip(eq, rng.normal(0, 0.25, 12)))
    filas, d = [], date(2025, 9, 1)
    for k in range(3):
        for h in eq:
            for a in eq:
                if h != a:
                    cl = rng.poisson(np.exp(np.log(5.3) + 0.1 + saca[h]))
                    cv = rng.poisson(np.exp(np.log(5.3) + saca[a]))
                    filas.append(esquinas.Fila(d, h, a, int(cl), int(cv), int(rng.poisson(2.2)), int(rng.poisson(2.4))))
            d = d + timedelta(days=3)
    m = esquinas.ModeloConteo("córners").ajustar(filas, date(2027, 1, 1), "c")
    est = [m.favor[e] for e in eq]
    assert np.corrcoef(est, list(saca.values()))[0, 1] > 0.8
    assert 9.5 < m.media_liga < 12.5 and m.dispersion < 1.3
    p = m.p_mas(10.6, 9.5)
    assert 0.5 < p < 0.75


if __name__ == "__main__":
    test_esquinas()
    print("OK  test_esquinas")
