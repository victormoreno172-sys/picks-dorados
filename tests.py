"""Pruebas rápidas sin internet:  python tests.py"""
from datetime import date

import numpy as np

import bot
import datos
from analisis import analizar
from demo import liga_simulada
from modelo import ModeloDixonColes, mercados

CSV_RESULTADOS = """﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,AvgH,AvgD,AvgA,Avg>2.5,Avg<2.5
SP1,15/08/2025,19:00,Girona,Vallecano,1,3,A,2.10,3.40,3.50,1.90,1.95
SP1,16/08/25,21:30,Villarreal,Oviedo,2,0,H,1.40,4.80,8.00,1.75,2.10
SP1,17/08/2025,,Mallorca,Barcelona,,,,6.0,4.5,1.5,1.6,2.3
"""
CSV_PROXIMOS = """Div,Date,Time,HomeTeam,AwayTeam,AvgH,AvgD,AvgA,Avg>2.5,Avg<2.5
SP1,14/10/2026,21:00,Betis,Sevilla,2.20,3.30,3.40,2.00,1.85
E0,14/10/2026,20:00,Arsenal,Chelsea,1.90,3.60,4.10,1.70,2.20
XX9,14/10/2026,20:00,Nadie,Ninguno,2,3,4,2,2
SP1,15/10/2026,21:00,Getafe,Elche,2.5,3.0,3.0,2.4,1.6
"""


def test_csv():
    r = datos.resultados_desde_csv(CSV_RESULTADOS)
    assert len(r) == 2 and r[0].local == "Girona" and r[1].fecha == date(2025, 8, 16)
    p = datos.proximos_desde_csv(CSV_PROXIMOS, date(2026, 10, 14))
    assert [x.local for x in p] == ["Betis", "Arsenal"]
    assert p[0].cuotas["Más de 2.5 goles"] == 2.0
    assert datos.codigo_temporada(date(2026, 10, 14)) == "2627"
    assert datos.codigo_temporada(date(2027, 3, 1)) == "2627"
    assert datos.emparejar_nombre("Real Betis", ["Betis", "Sevilla", "Ath Bilbao"]) == "Betis"


def test_modelo():
    partidos, reales = liga_simulada()
    m = ModeloDixonColes().ajustar(partidos)
    est = np.array([m.ataque[e] for e in reales])
    ver = np.array([reales[e][0] for e in reales])
    assert np.corrcoef(est, ver)[0, 1] > 0.8, "el modelo no recupera las fuerzas reales"
    p = mercados(m.tabla_marcadores("Atlético Norte", "Cádiz Arena"))
    assert abs(p["Gana local (1)"] + p["Empate (X)"] + p["Gana visitante (2)"] - 1) < 1e-9
    assert abs(p["Más de 2.5 goles"] + p["Menos de 2.5 goles"] - 1) < 1e-9
    assert p["Gana local (1)"] > 0.6


def test_bot_sin_telegram():
    partidos, _ = liga_simulada()
    m = ModeloDixonColes().ajustar(partidos)
    pp = datos.PartidoProximo("SP1", date.today(), "21:00", "Betis Sol", "Rayo Monte",
                              {"Gana local (1)": 2.0, "Empate (X)": 3.4, "Gana visitante (2)": 3.8})
    a = analizar(pp, m)
    s = sum(pk.prob for pk in a.picks if pk.mercado in ("Gana local (1)", "Empate (X)", "Gana visitante (2)"))
    assert abs(s - 1) < 1e-9
    enviados = []
    bot.enviar = lambda chat, t: enviados.append(t)
    bot._cache[bot.hoy()] = [a]
    bot.responder(1, "/partido 1")
    bot.responder(1, "/partido 9")
    bot.responder(1, "/ayuda")
    assert "Betis Sol" in enviados[0] and "número del 1 al 1" in enviados[1] and "Dorado" in enviados[2]


if __name__ == "__main__":
    for t in (test_csv, test_modelo, test_bot_sin_telegram):
        t()
        print(f"OK  {t.__name__}")
