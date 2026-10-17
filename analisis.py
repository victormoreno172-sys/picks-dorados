"""Une modelo + cuotas y genera los textos que se envían por Telegram."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from html import escape

import config
from datos import PartidoProximo
from modelo import ModeloDixonColes, marcador_mas_probable, mercados

GRUPOS_1X2 = ["Gana local (1)", "Empate (X)", "Gana visitante (2)"]
GRUPOS_OU = ["Más de 2.5 goles", "Menos de 2.5 goles"]


@dataclass
class Pick:
    mercado: str
    prob: float
    cuota: float | None = None
    prob_cuota: float | None = None  # probabilidad implícita (sin margen de la casa)
    estimada: bool = False           # cuota supuesta (p. ej. 1.91 estándar), no la real de la casa

    @property
    def dorado(self) -> bool:
        return self.prob >= config.UMBRAL_DORADO and self.mercado not in config.MERCADOS_TRIVIALES

    @property
    def rojo(self) -> bool:
        """Muy probable Y con una cuota real que todavía paga algo (desactivado en la app)."""
        return config.USAR_ROJO and (self.cuota is not None and not self.estimada
                and self.prob >= config.UMBRAL_ROJO_PROB and self.cuota >= config.UMBRAL_ROJO_CUOTA)

    @property
    def valor(self) -> bool:
        """La cuota REAL de la casa paga al menos un 5% más de lo que vale según la app
        (ganancia esperada = probabilidad × cuota − 1 ≥ 5%)."""
        return (self.cuota is not None and not self.estimada
                and self.prob * self.cuota - 1 >= config.UMBRAL_VALOR)

    @property
    def cuota_justa(self) -> float:
        return 1 / self.prob if self.prob > 0 else float("inf")


@dataclass
class Analisis:
    partido: PartidoProximo
    goles_local: float
    goles_visitante: float
    marcador: str
    prob_marcador: float
    picks: list[Pick] = field(default_factory=list)

    @property
    def destacados(self) -> list[Pick]:
        return sorted([p for p in self.picks if p.dorado or p.rojo], key=lambda p: (not p.rojo, -p.prob))


def _quitar_margen(cuotas: dict[str, float], grupo: list[str]) -> dict[str, float]:
    """Las cuotas llevan el margen de la casa. Lo quitamos normalizando a 100%."""
    if not all(m in cuotas for m in grupo):
        return {}
    inv = {m: 1 / cuotas[m] for m in grupo}
    s = sum(inv.values())
    return {m: v / s for m, v in inv.items()}


# Calibrado con cuotas reales de Winamax (Real Madrid - Sevilla, 17/10/2026): la casa no reparte
# su margen en proporción, sino casi a partes iguales entre las opciones (así el favorito paga
# casi lo justo y la opción poco probable paga bastante menos). Y no en todos los mercados se
# queda lo mismo: en "ambos marcan" se queda unas 2,5 veces más que en el total de goles.
FACTOR_MARGEN = (("Ambos marcan", 2.5), (" marca", 1.2), ("o empate", 0.67), ("No hay empate", 0.67))


def estimar_cuotas(picks: list["Pick"], prob_mercado: dict[str, float], margen: float):
    """Pone cuota estimada (≈) a los picks sin cuota, con la probabilidad que da la casa
    (deducida de sus cuotas reales) y su margen típico en mercados de dos opciones."""
    margen = min(0.08, max(0.03, margen))
    for pk in picks:
        if pk.cuota is None and pk.mercado in prob_mercado:
            pm = prob_mercado[pk.mercado]
            if 0.03 < pm < 0.97:
                f = next((v for clave, v in FACTOR_MARGEN if clave in pk.mercado), 1.0)
                pk.cuota = round(max(1.01, 1 / min(0.995, pm + f * margen / 2)), 2)
                pk.estimada = True


def goles_del_mercado(cuotas: dict[str, float]) -> tuple[float, float, float] | None:
    """
    Goles esperados de cada equipo que "piensa" la casa, deducidos de sus cuotas
    de 1X2 (y de más/menos 2.5 goles si las hay). Devuelve (λ local, μ visitante, margen).
    """
    import re as _re
    imp = _quitar_margen(cuotas, GRUPOS_1X2)
    if not imp:
        return None
    margen = sum(1 / cuotas[m] for m in GRUPOS_1X2) - 1
    objetivo = [imp[GRUPOS_1X2[0]], imp[GRUPOS_1X2[1]]]
    # Línea de goles de la casa: la que haya (en la MLS suele ser 3 o 3.5, no 2.5)
    lineas = sorted({float(m.group(1)) for k in cuotas for m in [_re.match(r"Más de ([\d.]+) goles$", k)] if m
                     and f"Menos de {m.group(1)} goles" in cuotas}, key=lambda x: abs(x - 2.5))
    ou = None
    if lineas:
        lin = lineas[0]
        txt = f"{lin:g}"
        po, pu = 1 / cuotas[f"Más de {txt} goles"], 1 / cuotas[f"Menos de {txt} goles"]
        ou = (lin, po / (po + pu))
        objetivo.append(ou[1])
        margen_2 = po + pu - 1  # margen real de la casa en un mercado de dos opciones
    else:
        margen_2 = None

    import numpy as np
    from scipy.optimize import minimize
    from scipy.stats import poisson

    g = np.arange(11)

    def probs(x):
        lam, mu = np.exp(x)
        m = np.outer(poisson.pmf(g, lam), poisson.pmf(g, mu))
        i, j = np.indices(m.shape)
        out = [m[i > j].sum(), m[i == j].sum()]
        if ou:
            lin, t = ou[0], i + j
            if abs(lin - round(lin)) < 1e-9:  # línea entera: si cae justo, se devuelve (push)
                mas, igual = m[t > lin].sum(), m[t == lin].sum()
                out.append(mas / max(1e-9, 1 - igual))
            elif abs(lin * 4 - round(lin * 4)) < 1e-9 and abs(lin * 2 - round(lin * 2)) > 1e-9:
                # línea asiática de cuarto (2.25, 2.75): media de las dos líneas vecinas
                a1, a2 = lin - 0.25, lin + 0.25
                def p_l(l):
                    if abs(l - round(l)) < 1e-9:
                        return m[t > l].sum() / max(1e-9, 1 - m[t == l].sum())
                    return m[t > l].sum()
                out.append((p_l(a1) + p_l(a2)) / 2)
            else:
                out.append(m[t > lin].sum())
        return np.array(out)

    res = minimize(lambda x: np.sum((probs(x) - objetivo) ** 2), np.log([1.4, 1.1]), method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-10})
    lam, mu = np.exp(res.x)
    if res.fun > 1e-3:  # cuotas incoherentes: mejor no usarlas
        return None
    # Margen para los mercados de dos opciones (los que estimamos): el de su línea de goles si
    # la hay; si no, uno típico deducido del 1X2 (que tiene tres opciones y más margen).
    if margen_2 is None or not (0 < margen_2 < 0.15):
        margen_2 = min(0.07, max(0.03, margen * 2 / 3))
    return float(lam), float(mu), float(margen_2)


def analizar(p: PartidoProximo, modelo: ModeloDixonColes) -> Analisis | None:
    if not (modelo.conoce(p.local) and modelo.conoce(p.visitante)):
        return None  # equipo recién ascendido sin historial suficiente, etc.
    tabla = modelo.tabla_marcadores(p.local, p.visitante)
    probs = mercados(tabla)
    lam, mu = modelo.goles_esperados(p.local, p.visitante)
    w = config.PESO_MERCADO

    cuotas = dict(p.cuotas)
    estimadas: set[str] = set()
    implicitas = {**_quitar_margen(cuotas, GRUPOS_1X2), **_quitar_margen(cuotas, GRUPOS_OU)}
    mercado = goles_del_mercado(cuotas)
    if mercado:
        # La casa "dice" unos goles esperados: con ellos sale su tabla de marcadores y,
        # de ahí, su opinión sobre TODOS los mercados de goles.
        lm, mm, margen = mercado
        from scipy.stats import poisson
        import numpy as np
        g = np.arange(11)
        tabla_m = np.outer(poisson.pmf(g, lm), poisson.pmf(g, mm))
        tabla_m /= tabla_m.sum()
        prob_mercado = mercados(tabla_m)
        # Mezcla modelo + mercado en todos los mercados (el mercado sabe de lesiones, rotaciones...)
        tabla = (1 - w) * tabla + w * tabla_m
        final = {m: (1 - w) * probs[m] + w * prob_mercado[m] for m in probs}
        # Cuotas estimadas (≈) para los mercados que la casa no nos ha dado, con su mismo margen
        for m, pm_ in prob_mercado.items():
            if m not in cuotas and 0.02 < pm_ < 0.98:
                cuotas[m] = round(max(1.01, 1 / (pm_ * (1 + margen))), 2)
                estimadas.add(m)
        lam, mu = (1 - w) * lam + w * lm, (1 - w) * mu + w * mm
    else:
        final = dict(probs)
        for m, pi in implicitas.items():
            final[m] = (1 - w) * probs[m] + w * pi
        if all(m in implicitas for m in GRUPOS_OU):
            final["Menos de 2.5 goles"] = 1 - final["Más de 2.5 goles"]

    if all(m in cuotas for m in GRUPOS_1X2) and not mercado:
        c1, cx, c2 = (cuotas[m] for m in GRUPOS_1X2)
        for m, c in (("Local o empate (1X)", 1 / (1 / c1 + 1 / cx)), ("Visitante o empate (X2)", 1 / (1 / c2 + 1 / cx)),
                     ("No hay empate (12)", 1 / (1 / c1 + 1 / c2))):
            if m not in cuotas:
                cuotas[m] = round(c, 2)
                estimadas.add(m)
    if all(m in implicitas for m in GRUPOS_1X2):
        implicitas["Local o empate (1X)"] = implicitas[GRUPOS_1X2[0]] + implicitas[GRUPOS_1X2[1]]
        implicitas["Visitante o empate (X2)"] = implicitas[GRUPOS_1X2[2]] + implicitas[GRUPOS_1X2[1]]
        implicitas["No hay empate (12)"] = implicitas[GRUPOS_1X2[0]] + implicitas[GRUPOS_1X2[2]]

    marcador, pm = marcador_mas_probable(tabla)
    picks = [Pick(m, v, cuotas.get(m), None if m in estimadas else implicitas.get(m), estimada=m in estimadas)
             for m, v in final.items()]
    return Analisis(p, lam, mu, marcador, pm, picks)


# ------------------------------------------------------------------ formato
def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _linea_pick(pk: Pick) -> str:
    icono = "🔴" if pk.rojo else ("🟡" if pk.dorado else "▫️")
    txt = f"{icono} {escape(pk.mercado)}: <b>{_pct(pk.prob)}</b>"
    if pk.cuota:
        txt += f" · cuota {pk.cuota:.2f}"
    if pk.valor:
        txt += " 💎"
    return txt


def resumen_del_dia(analisis: list[Analisis], dia: date) -> list[str]:
    """Mensaje del día. Devuelve una lista porque Telegram corta a 4096 caracteres."""
    cab = (f"⚽ <b>Partidos del {dia.strftime('%d/%m/%Y')}</b>\n"
           f"🟡 = probabilidad ≥ {_pct(config.UMBRAL_DORADO)} · 💎 = la cuota paga ≥5% más de lo que vale\n")
    if not analisis:
        return [cab + "\nHoy no hay partidos de las ligas que seguimos."]

    bloques = []
    for n, a in enumerate(analisis, 1):
        p = a.partido
        liga = config.nombre_liga(p.liga)
        b = (f"\n<b>{n}. {escape(p.local)} – {escape(p.visitante)}</b>\n"
             f"{liga} · {p.hora or 'hora por confirmar'}\n"
             f"Goles esperados {a.goles_local:.1f} – {a.goles_visitante:.1f}\n")
        top = a.destacados[:3]
        if top:
            b += "\n".join(_linea_pick(pk) for pk in top) + "\n"
        else:
            b += "Sin picks por encima del umbral.\n"
        bloques.append(b)

    pie = (f"\nEscribe /partido N para ver todos los mercados.\n"
           f"<i>Son estimaciones estadísticas, no certezas. Juega con responsabilidad (+18).</i>")

    mensajes, actual = [], cab
    for b in bloques + [pie]:
        if len(actual) + len(b) > 3900:
            mensajes.append(actual)
            actual = ""
        actual += b
    mensajes.append(actual)
    return mensajes


def detalle_partido(a: Analisis) -> str:
    p = a.partido
    orden = sorted(a.picks, key=lambda pk: -pk.prob)
    lineas = "\n".join(_linea_pick(pk) + f" <i>(justa {pk.cuota_justa:.2f})</i>" for pk in orden)
    return (f"<b>{escape(p.local)} – {escape(p.visitante)}</b>\n"
            f"{config.nombre_liga(p.liga)} · {p.hora or 'hora por confirmar'}\n"
            f"Goles esperados {a.goles_local:.2f} – {a.goles_visitante:.2f}\n"
            f"Marcador más probable: {a.marcador} ({_pct(a.prob_marcador)})\n\n"
            f"{lineas}\n\n"
            f"<i>Cuota justa = la cuota mínima para que la apuesta tenga sentido según nuestra probabilidad.</i>")
