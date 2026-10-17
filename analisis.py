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


# Calibrado con cuotas reales de Winamax (capturas de Real Madrid - Sevilla y Leeds - Man United,
# Racing - Independiente y Forest - Arsenal, 17/10/2026): la casa no reparte su margen en proporción, sino casi a partes iguales entre las
# opciones (el favorito paga casi lo justo y la opción poco probable bastante menos). Y no se queda
# lo mismo en todos los mercados. Factor = cuánto margen respecto al de más/menos 2.5 goles.
FACTOR_MARGEN = (("Ambos marcan", 1.0), (" marca", 1.5))  # "Local marca"/"Visitante marca" (no "Ambos marcan", que va como el resto)


# Las casas cuentan con más empates y marcadores cortos (0-0, 1-1) de los que da un Poisson puro:
# corrección de Dixon-Coles. Con -0.07 las cuotas de goles deducidas solo del 1X2 cuadran con
# Winamax (Racing - Independiente, sin línea de goles en la API).
RHO_MERCADO = -0.07


def tabla_mercado(lam: float, mu: float, rho: float = RHO_MERCADO):
    import numpy as np
    from scipy.stats import poisson
    g = np.arange(11)
    m = np.outer(poisson.pmf(g, lam), poisson.pmf(g, mu))
    m[0, 0] *= 1 - lam * mu * rho
    m[0, 1] *= 1 + lam * rho
    m[1, 0] *= 1 + mu * rho
    m[1, 1] *= 1 - rho
    return m / m.sum()


def cuota_estimada(mercado: str, pm: float, margen: float) -> float:
    """Cuota que pondría la casa a un mercado de probabilidad pm (sin margen)."""
    margen = min(0.08, max(0.03, margen))
    f = next((v for clave, v in FACTOR_MARGEN if clave in mercado), 1.0)
    return round(max(1.01, 1 / min(0.995, pm + f * margen / 2)), 2)


def estimar_cuotas(picks: list["Pick"], prob_mercado: dict[str, float], margen: float):
    """Pone cuota estimada (≈) a los picks sin cuota, con la probabilidad que da la casa
    (deducida de sus cuotas reales) y su margen típico en mercados de dos opciones."""
    margen = min(0.08, max(0.03, margen))
    for pk in picks:
        if pk.cuota is None and pk.mercado in prob_mercado:
            pm = prob_mercado[pk.mercado]
            if 0.03 < pm < 0.97:
                pk.cuota = cuota_estimada(pk.mercado, pm, margen)
                pk.estimada = True


def goles_del_mercado(cuotas: dict[str, float], total_modelo: float | None = None) -> tuple[float, float, float] | None:
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
        m = tabla_mercado(lam, mu)
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

    # Sin línea de goles de la casa, el 1X2 solo no dice bien cuántos goles habrá (Racing - Independiente
    # y Belgrano - River tenían 1X2 parecidos y totales muy distintos): se usa el total de nuestro
    # modelo como referencia y el 1X2 decide quién marca más.
    usa_total = ou is None and total_modelo
    opciones = {"xatol": 1e-6, "fatol": 1e-10}
    res = minimize(lambda x: np.sum((probs(x) - objetivo) ** 2), np.log([1.4, 1.1]), method="Nelder-Mead", options=opciones)
    if usa_total:
        # a medio camino entre lo que sugiere el 1X2 y lo que dice nuestro modelo (con 5 partidos
        # de prueba es lo que más se acerca a las cuotas de goles reales de Winamax)
        objetivo_total = (np.exp(res.x).sum() + total_modelo) / 2
        res = minimize(lambda x: np.sum((probs(x) - objetivo) ** 2) + (np.exp(x).sum() / objetivo_total - 1) ** 2,
                       res.x, method="Nelder-Mead", options=opciones)
    lam, mu = np.exp(res.x)
    if res.fun > (3e-3 if usa_total else 1e-3):  # cuotas incoherentes: mejor no usarlas
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
    # Control de seguridad: si las cuotas de la casa dicen lo contrario que nuestro modelo
    # (p. ej. el favorito al revés), lo más probable es que se hayan emparejado con otro partido
    # o con local/visitante cambiados. Si al darles la vuelta cuadran, se giran; si no, se descartan.
    imp = _quitar_margen(cuotas, GRUPOS_1X2)
    if imp:
        p1, p2 = probs["Gana local (1)"], probs["Gana visitante (2)"]
        d = abs(imp[GRUPOS_1X2[0]] - p1) + abs(imp[GRUPOS_1X2[2]] - p2)
        d_giro = abs(imp[GRUPOS_1X2[2]] - p1) + abs(imp[GRUPOS_1X2[0]] - p2)
        if d > 0.6:
            if d_giro < 0.3:
                print(f"  aviso cuotas: {p.local} - {p.visitante} venían al revés, se giran")
                cuotas[GRUPOS_1X2[0]], cuotas[GRUPOS_1X2[2]] = cuotas[GRUPOS_1X2[2]], cuotas[GRUPOS_1X2[0]]
            else:
                print(f"  aviso cuotas: {p.local} - {p.visitante} no cuadran con el modelo, se ignoran")
                cuotas = {}
                p.casa = ""
    estimadas: set[str] = set()
    implicitas = {**_quitar_margen(cuotas, GRUPOS_1X2), **_quitar_margen(cuotas, GRUPOS_OU)}
    mercado = goles_del_mercado(cuotas, lam + mu)
    if mercado:
        # La casa "dice" unos goles esperados: con ellos sale su tabla de marcadores y,
        # de ahí, su opinión sobre TODOS los mercados de goles.
        lm, mm, margen = mercado
        tabla_m = tabla_mercado(lm, mm)
        prob_mercado = mercados(tabla_m)
        # Mezcla modelo + mercado en todos los mercados (el mercado sabe de lesiones, rotaciones...)
        tabla = (1 - w) * tabla + w * tabla_m
        final = {m: (1 - w) * probs[m] + w * prob_mercado[m] for m in probs}
        # Cuotas estimadas (≈) para los mercados que la casa no nos ha dado, con su mismo margen
        for m, pm_ in prob_mercado.items():
            if m not in cuotas and 0.02 < pm_ < 0.98:
                cuotas[m] = cuota_estimada(m, pm_, margen)
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
