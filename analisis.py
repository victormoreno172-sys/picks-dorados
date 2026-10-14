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

    @property
    def dorado(self) -> bool:
        return self.prob >= config.UMBRAL_DORADO and self.mercado not in config.MERCADOS_TRIVIALES

    @property
    def valor(self) -> bool:
        return self.prob_cuota is not None and self.prob - self.prob_cuota >= config.UMBRAL_VALOR

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
        return sorted([p for p in self.picks if p.dorado], key=lambda p: -p.prob)


def _quitar_margen(cuotas: dict[str, float], grupo: list[str]) -> dict[str, float]:
    """Las cuotas llevan el margen de la casa. Lo quitamos normalizando a 100%."""
    if not all(m in cuotas for m in grupo):
        return {}
    inv = {m: 1 / cuotas[m] for m in grupo}
    s = sum(inv.values())
    return {m: v / s for m, v in inv.items()}


def analizar(p: PartidoProximo, modelo: ModeloDixonColes) -> Analisis | None:
    if not (modelo.conoce(p.local) and modelo.conoce(p.visitante)):
        return None  # equipo recién ascendido sin historial suficiente, etc.
    tabla = modelo.tabla_marcadores(p.local, p.visitante)
    probs = mercados(tabla)
    lam, mu = modelo.goles_esperados(p.local, p.visitante)
    marcador, pm = marcador_mas_probable(tabla)

    implicitas = {**_quitar_margen(p.cuotas, GRUPOS_1X2), **_quitar_margen(p.cuotas, GRUPOS_OU)}

    # Mezcla modelo + mercado: el mercado sabe cosas que el modelo no (lesiones, rotaciones).
    w = config.PESO_MERCADO
    final = dict(probs)
    for m, pi in implicitas.items():
        final[m] = (1 - w) * probs[m] + w * pi
    if all(m in implicitas for m in GRUPOS_1X2):
        final["Local o empate (1X)"] = final[GRUPOS_1X2[0]] + final[GRUPOS_1X2[1]]
        final["Visitante o empate (X2)"] = final[GRUPOS_1X2[2]] + final[GRUPOS_1X2[1]]
        final["No hay empate (12)"] = final[GRUPOS_1X2[0]] + final[GRUPOS_1X2[2]]
    if all(m in implicitas for m in GRUPOS_OU):
        final["Menos de 2.5 goles"] = 1 - final["Más de 2.5 goles"]

    picks = [Pick(m, v, p.cuotas.get(m), implicitas.get(m)) for m, v in final.items()]
    return Analisis(p, lam, mu, marcador, pm, picks)


# ------------------------------------------------------------------ formato
def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _linea_pick(pk: Pick) -> str:
    icono = "🟡" if pk.dorado else "▫️"
    txt = f"{icono} {escape(pk.mercado)}: <b>{_pct(pk.prob)}</b>"
    if pk.cuota:
        txt += f" · cuota {pk.cuota:.2f}"
    if pk.valor:
        txt += " 💎"
    return txt


def resumen_del_dia(analisis: list[Analisis], dia: date) -> list[str]:
    """Mensaje del día. Devuelve una lista porque Telegram corta a 4096 caracteres."""
    cab = (f"⚽ <b>Partidos del {dia.strftime('%d/%m/%Y')}</b>\n"
           f"🟡 = probabilidad ≥ {_pct(config.UMBRAL_DORADO)} · 💎 = mejor que la cuota\n")
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
