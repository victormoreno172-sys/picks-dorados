"""
Auditoría con datos reales (se ejecuta en GitHub y deja el informe en web/auditoria.txt).

1. Fútbol: simulación de la temporada pasada sin trampas (cada partido se predice
   solo con datos anteriores) y comparación con el resultado real y con las cuotas
   de cierre de las casas. Mide qué mezcla modelo/cuotas acierta más.
2. Basket, tenis y esports: el modelo frente a las cuotas de la casa en los
   partidos próximos (para detectar fallos de orientación o modelos desviados).
"""
from __future__ import annotations

import csv
import io
import json
import math
from collections import defaultdict
from datetime import date, timedelta

import numpy as np

import config
import datos
from modelo import ModeloDixonColes, Partido, mercados

HOY = date.today()


def log_loss(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def cuotas_cierre(liga: str) -> list[dict]:
    """Partidos con resultado y cuotas medias (de cierre si las hay) de las 2 últimas temporadas."""
    out = []
    inicio = int(datos.codigo_temporada(HOY)[:2])
    for k in (1, 0):
        a = (inicio - k) % 100
        temp = f"{a:02d}{(a + 1) % 100:02d}"
        try:
            texto = datos._descargar(datos.URL_RESULTADOS.format(temp=temp, liga=liga), f"{liga}_{temp}.csv",
                                     24 * 30 if k else 6)
        except Exception:
            continue
        for f in csv.DictReader(io.StringIO(texto)):
            try:
                if f.get("FTHG") in (None, ""):
                    continue
                c = {}
                for nombre, cols in (("H", ("AvgCH", "AvgH", "B365H")), ("D", ("AvgCD", "AvgD", "B365D")),
                                     ("A", ("AvgCA", "AvgA", "B365A")), ("O", ("AvgC>2.5", "Avg>2.5", "B365>2.5")),
                                     ("U", ("AvgC<2.5", "Avg<2.5", "B365<2.5"))):
                    for col in cols:
                        if f.get(col):
                            c[nombre] = float(f[col])
                            break
                out.append({"fecha": datos._fecha(f["Date"]), "l": f["HomeTeam"].strip(), "v": f["AwayTeam"].strip(),
                            "gl": int(float(f["FTHG"])), "gv": int(float(f["FTAG"])), "c": c})
            except (ValueError, KeyError):
                continue
    return sorted(out, key=lambda x: x["fecha"])


def auditar_futbol(liga: str):
    filas = cuotas_cierre(liga)
    hist = datos.historico(liga, HOY)
    partidos = [Partido(p.fecha, p.local, p.visitante, p.goles_local, p.goles_visitante) for p in hist]
    desde = HOY - timedelta(days=330)
    test = [f for f in filas if f["fecha"] >= desde and {"H", "D", "A", "O", "U"} <= set(f["c"])]
    if len(test) < 100:
        print(f"{liga}: pocos partidos de prueba ({len(test)})")
        return None
    pesos = (0.0, 0.3, 0.5, 0.7, 0.85, 1.0)
    perdida = defaultdict(float)
    n = 0
    tramos = defaultdict(lambda: [0, 0.0, 0])  # calibración de la mezcla 0.5 y 0.7
    modelo, fecha_modelo = None, None
    for f in test:
        if modelo is None or (f["fecha"] - fecha_modelo).days >= 14:
            try:
                modelo = ModeloDixonColes().ajustar(partidos, hasta=f["fecha"])
                fecha_modelo = f["fecha"]
            except ValueError:
                continue
        if not (modelo.conoce(f["l"]) and modelo.conoce(f["v"])):
            continue
        pm = mercados(modelo.tabla_marcadores(f["l"], f["v"]))
        c = f["c"]
        s3 = 1 / c["H"] + 1 / c["D"] + 1 / c["A"]
        mk = {"1": 1 / c["H"] / s3, "X": 1 / c["D"] / s3, "2": 1 / c["A"] / s3}
        s2 = 1 / c["O"] + 1 / c["U"]
        mo = 1 / c["O"] / s2
        res = "1" if f["gl"] > f["gv"] else "X" if f["gl"] == f["gv"] else "2"
        over = f["gl"] + f["gv"] > 2.5
        md = {"1": pm["Gana local (1)"], "X": pm["Empate (X)"], "2": pm["Gana visitante (2)"]}
        for w in pesos:
            for r in "1X2":
                perdida[("1x2", w)] += log_loss((1 - w) * md[r] + w * mk[r], res == r)
            perdida[("ou", w)] += log_loss((1 - w) * pm["Más de 2.5 goles"] + w * mo, over)
        # calibración de "más de 1.5", "1X", etc. con la mezcla 0.5 (lo que muestra la app)
        for nombre in ("Más de 1.5 goles", "Local o empate (1X)", "Visitante o empate (X2)", "Menos de 3.5 goles",
                       "Ambos marcan: Sí", "Local marca", "Visitante marca", "Más de 2.5 goles"):
            p = pm[nombre]
            ok = {"Más de 1.5 goles": f["gl"] + f["gv"] > 1.5, "Local o empate (1X)": f["gl"] >= f["gv"],
                  "Visitante o empate (X2)": f["gl"] <= f["gv"], "Menos de 3.5 goles": f["gl"] + f["gv"] < 3.5,
                  "Ambos marcan: Sí": f["gl"] > 0 and f["gv"] > 0, "Local marca": f["gl"] > 0,
                  "Visitante marca": f["gv"] > 0, "Más de 2.5 goles": over}[nombre]
            t = min(int(p * 10), 9)
            tramos[t][0] += 1
            tramos[t][1] += p
            tramos[t][2] += ok
        n += 1
    print(f"\n=== {config.nombre_liga(liga)}: {n} partidos simulados (temporada pasada + actual)")
    for mercado in ("1x2", "ou"):
        fila = "  ".join(f"w={w:.2f}: {perdida[(mercado, w)] / n:.4f}" for w in pesos)
        mejor = min(pesos, key=lambda w: perdida[(mercado, w)])
        print(f"  pérdida {mercado} (menor = mejor): {fila}   -> mejor peso de las cuotas {mejor}")
    print("  calibración del modelo solo (mercados de goles): tramo, n, dijo, pasó")
    for t in sorted(tramos):
        k, sp, ok = tramos[t]
        if k >= 30:
            print(f"    {t * 10}-{t * 10 + 10}%: {k:5d}  {sp / k:6.1%}  {ok / k:6.1%}")
    return {mercado: min(pesos, key=lambda w: perdida[(mercado, w)]) for mercado in ("1x2", "ou")}


def comparar_con_mercado(nombre, filas):
    """filas: (prob modelo, prob mercado sin margen, etiqueta)"""
    if not filas:
        print(f"\n=== {nombre}: sin partidos con cuotas para comparar")
        return
    pm = np.array([f[0] for f in filas])
    pk = np.array([f[1] for f in filas])
    print(f"\n=== {nombre}: {len(filas)} partidos con cuota de la casa")
    print(f"  correlación modelo-casa {np.corrcoef(pm, pk)[0, 1]:.2f}, diferencia media {np.mean(np.abs(pm - pk)):.3f}, "
          f"sesgo (modelo - casa) {np.mean(pm - pk):+.3f}")
    peores = sorted(filas, key=lambda f: -abs(f[0] - f[1]))[:6]
    for f in peores:
        print(f"    mayor diferencia: {f[2]}  modelo {f[0]:.0%}  casa {f[1]:.0%}")


def auditar_otros():
    import cuotas as cmod
    ev = cmod.instancia(HOY)
    # --- Basket
    try:
        import baloncesto as bb
        for nombre, juegos in (("NBA", bb.nba_temporada_pasada(HOY) + bb.nba_temporada_actual(HOY, 7)),
                               ("Basket Europa", bb.europa(HOY, 7))):
            prox = [j for j in juegos if not j.jugado and HOY <= j.fecha < HOY + timedelta(days=7)]
            if not prox:
                continue
            m = bb.ModeloBaloncesto().ajustar(juegos, hasta=HOY)
            filas = []
            for j in prox:
                if not (m.conoce(j.local_id) and m.conoce(j.visit_id)):
                    continue
                e = ev.buscar(j.comp, j.fecha, j.local, j.visitante)
                if not e or "Gana local" not in e.cuotas or "Gana visitante" not in e.cuotas:
                    continue
                pl, pv = m.esperado(j)
                from scipy.stats import norm
                p_mod = float(norm.sf(0, loc=pl - pv, scale=m.sd_margen))
                c1, c2 = e.cuotas["Gana local"], e.cuotas["Gana visitante"]
                filas.append((p_mod, (1 / c1) / (1 / c1 + 1 / c2),
                              f"{j.local} - {j.visitante} (casa: {e.local} - {e.visitante}, spread {e.spread_local})"))
            comparar_con_mercado(nombre, filas)
    except Exception as e:
        import traceback
        traceback.print_exc()
    # --- Tenis
    try:
        import tenis
        for tour in tenis.TOURS:
            hist = tenis.historico(tour, HOY)
            elo = tenis.EloTenis(tour).ajustar(hist)
            filas = []
            for p in tenis.proximos(tour, HOY, 7):
                if not (elo.conoce(p.j1) and elo.conoce(p.j2)):
                    continue
                e = ev.buscar(tour, p.fecha, p.n1, p.n2)
                if not e:
                    continue
                c1, c2 = e.cuotas.get("Gana local"), e.cuotas.get("Gana visitante")
                if not (c1 and c2):
                    continue
                filas.append((elo.p_partido(p.j1, p.j2, tenis.superficie(p.torneo, p.fecha)),
                              (1 / c1) / (1 / c1 + 1 / c2), f"{p.n1} - {p.n2}"))
            comparar_con_mercado(f"Tenis {tour}", filas)
    except Exception:
        import traceback
        traceback.print_exc()
    # --- Esports
    try:
        import esports as es
        for juego in es.JUEGOS:
            hist = es.historico(juego, HOY)
            m = es.ModeloMapas().ajustar(hist, HOY)
            filas = []
            for s in es.proximos(juego, HOY, 7):
                cg = es._cuotas_ganador(s)
                if not cg or not (m.conoce(s.eq1) and m.conoce(s.eq2)):
                    continue
                k = s.bo // 2 + 1
                p = m.p_mapa(s.eq1, s.eq2)
                p_mod = sum(v for (x, y), v in es.marcadores(p, s.bo).items() if x == k)
                filas.append((p_mod, (1 / cg[0]) / (1 / cg[0] + 1 / cg[1]), f"{s.n1} - {s.n2}"))
            comparar_con_mercado(f"Esports {juego}", filas)
    except Exception:
        import traceback
        traceback.print_exc()


def auditar_esquinas(liga: str):
    import esquinas
    filas = esquinas.historico(liga, HOY)
    test = [f for f in filas if f.fecha >= HOY - timedelta(days=330)]
    for campo, lineas, nombre in (("c", esquinas.LINEAS_CORNERS, "córners"), ("t", esquinas.LINEAS_TARJETAS, "tarjetas")):
        tramos = defaultdict(lambda: [0, 0.0, 0])
        m, fm = None, None
        for f in test:
            if m is None or (f.fecha - fm).days >= 21:
                try:
                    m = esquinas.ModeloConteo(nombre).ajustar(filas, f.fecha, campo)
                    fm = f.fecha
                except ValueError:
                    continue
            if not (m.conoce(f.local) and m.conoce(f.visitante)):
                continue
            a, b = m.esperado(f.local, f.visitante)
            tot = getattr(f, campo + "l") + getattr(f, campo + "v")
            for lin in lineas:
                p = m.p_mas(a + b, lin)
                for q, ok in ((p, tot > lin), (1 - p, tot < lin)):
                    t = min(int(q * 10), 9)
                    tramos[t][0] += 1
                    tramos[t][1] += q
                    tramos[t][2] += ok
        print(f"\n=== {nombre} {liga}: tramo, n, dijo, pasó")
        for t in sorted(tramos):
            k, sp, ok = tramos[t]
            if k >= 30:
                print(f"    {t * 10}-{t * 10 + 10}%: {k:5d}  {sp / k:6.1%}  {ok / k:6.1%}")


if __name__ == "__main__":
    for liga in ("SP1", "E0", "I1", "D1", "F1", "E1"):
        try:
            auditar_esquinas(liga)
        except Exception:
            import traceback
            traceback.print_exc()
    resumen = {}
    for liga in ("SP1", "E0", "I1", "D1", "F1", "E1"):
        try:
            resumen[liga] = auditar_futbol(liga)
        except Exception:
            import traceback
            traceback.print_exc()
    print("\nMEJOR PESO DE LAS CUOTAS POR LIGA:", json.dumps(resumen))
    auditar_otros()
