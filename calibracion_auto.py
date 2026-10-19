"""
Calibración automática del bot con los resultados reales.

La app guarda el resultado de cada pronóstico (historial). En cada ejecución se mira, por deporte y
tipo de mercado, si lo que el modelo decía se cumple: p. ej. "Menos de X goles" al 72 % de media
¿acierta el 72 % o el 65 %? Con esa diferencia se corrigen las probabilidades ANTES de que el bot
elija. La corrección es prudente: con pocos datos casi no toca nada y crece con la muestra
(peso n / (n + N0)), y nunca pasa de ±MAX_LOGIT en escala logit.

Si un mercado falla de forma repetida, su probabilidad corregida baja y deja de pasar los filtros
del bot (70 % y valor de la cuota) sin tener que tocar nada a mano.
"""
from __future__ import annotations

import math
import re

N0 = 100        # con 100 picks la corrección pesa la mitad; con 300, tres cuartos
MIN_N = 20      # por debajo, nada
MAX_LOGIT = 0.5

FAMILIAS = [
    (r"^Más de [\d.]+ goles", "Más de X goles"), (r"^Menos de [\d.]+ goles", "Menos de X goles"),
    (r"^Más de [\d.]+ puntos", "Más de X puntos"), (r"^Menos de [\d.]+ puntos", "Menos de X puntos"),
    (r"^Hándicap", "Hándicap"), (r"\((1X|X2|12)\)$", "Doble oportunidad"), (r"\((1|X|2)\)$", "1X2"),
    (r"^Ambos marcan", "Ambos marcan"), (r"marca$", "Marca un equipo"),
    (r"^(Más|Menos) de [\d.]+ sets", "Total de sets"), (r"[+-][\d.]+ sets$", "Hándicap de sets"),
    (r"^(Más|Menos) de [\d.]+ (mapas|partidas)", "Total de mapas"), (r"[+-][\d.]+ (mapas|partidas)$", "Hándicap de mapas"),
    (r"^Resultado ", "Resultado exacto"), (r"^Gana ", "Ganador"),
]
NOMBRE_DEP = {"f": "Fútbol", "b": "Basket", "te": "Tenis", "e": "Esports"}


def familia(mercado: str) -> str:
    for pat, nombre in FAMILIAS:
        if re.search(pat, mercado):
            return nombre
    return "Otros"


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def tabla(h: dict | None = None, banca: dict | None = None) -> dict:
    """{(dep, familia): {"n", "prevista", "real", "delta", "peso"}} con los picks ya corregidos."""
    if h is None:
        import historial
        h = historial.cargar()
    grupos: dict[tuple, list] = {}
    for e in (h.get("partidos") or {}).values():
        dep = e.get("dep", "f")
        for k in e.get("picks") or []:
            if "ok" not in k or k.get("ok") is None or float(k.get("p") or 0) < 0.5:
                continue  # solo lo que el bot podría elegir (lado favorito)
            grupos.setdefault((dep, familia(k["m"])), []).append((float(k["p"]), bool(k["ok"])))
    # Las piernas de las apuestas del bot que no estén ya en el historial (mercados que no salen en dorado)
    vistos = {(e.get("f"), e.get("l"), e.get("v"), k.get("m")) for e in (h.get("partidos") or {}).values() for k in e.get("picks") or []}
    for ap in (banca or {}).get("apuestas") or []:
        for pi in ap.get("piernas") or []:
            if pi.get("ok") is None or (pi.get("fecha"), pi.get("local"), pi.get("visitante"), pi.get("mercado")) in vistos:
                continue
            grupos.setdefault((pi.get("dep", "f"), familia(pi["mercado"])), []).append((float(pi.get("prob") or 0), bool(pi["ok"])))
    out = {}
    for clave, xs in grupos.items():
        n = len(xs)
        prev = sum(p for p, _ in xs) / n
        real = sum(1 for _, o in xs if o) / n
        # real suavizado (evita 0 % o 100 % con pocos datos)
        real_s = (sum(1 for _, o in xs if o) + 2 * prev) / (n + 2)
        delta = max(-MAX_LOGIT, min(MAX_LOGIT, _logit(real_s) - _logit(prev)))
        peso = n / (n + N0) if n >= MIN_N else 0.0
        out[clave] = {"n": n, "prevista": round(prev, 3), "real": round(real, 3),
                      "delta": round(delta * peso, 3), "peso": round(peso, 2)}
    return out


def ajustar(p: float, dep: str, mercado: str, t: dict) -> float:
    g = t.get((dep, familia(mercado)))
    if not g or not g["delta"] or p <= 0 or p >= 1:
        return p
    z = _logit(p) + g["delta"]
    return 1 / (1 + math.exp(-z))


def informe(t: dict) -> list[dict]:
    """Para la app del bot: cada grupo con su corrección."""
    filas = []
    for (dep, fam), g in sorted(t.items(), key=lambda kv: -kv[1]["n"]):
        filas.append({"dep": dep, "dep_n": NOMBRE_DEP.get(dep, dep), "mercado": fam, **g,
                      "efecto": round(ajustar_desde(0.75, g["delta"]), 3)})  # qué pasa con un 75 %
    return filas


def ajustar_desde(p: float, delta: float) -> float:
    return 1 / (1 + math.exp(-(_logit(p) + delta)))
