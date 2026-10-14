"""
Modelo Dixon-Coles para estimar probabilidades de partidos de fútbol.

Idea:
  - Cada equipo tiene una fuerza de ATAQUE y una de DEFENSA.
  - Goles esperados del local    = exp(ataque_local + defensa_visitante + factor_campo)
  - Goles esperados del visitante = exp(ataque_visitante + defensa_local)
  - Los goles siguen una distribución de Poisson, con la corrección de
    Dixon-Coles (rho) para los marcadores bajos (0-0, 1-0, 0-1, 1-1).
  - Los partidos recientes pesan más que los antiguos (decaimiento temporal).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

MAX_GOLES = 10  # tamaño de la tabla de marcadores (0..10 goles por equipo)


@dataclass
class Partido:
    fecha: date
    local: str
    visitante: str
    goles_local: int
    goles_visitante: int


class ModeloDixonColes:
    def __init__(self, xi: float = 0.0019):
        # xi = velocidad de olvido. 0.0019/día ≈ un partido de hace 1 año pesa ~50%.
        self.xi = xi
        self.equipos: list[str] = []
        self.ataque: dict[str, float] = {}
        self.defensa: dict[str, float] = {}
        self.campo = 0.25
        self.rho = -0.05
        self.ajustado = False

    # ------------------------------------------------------------------ ajuste
    def ajustar(self, partidos: list[Partido], hasta: date | None = None) -> "ModeloDixonColes":
        if hasta is not None:
            partidos = [p for p in partidos if p.fecha < hasta]
        if len(partidos) < 30:
            raise ValueError(f"Muy pocos partidos para ajustar el modelo ({len(partidos)}).")

        ref = hasta or max(p.fecha for p in partidos)
        self.equipos = sorted({p.local for p in partidos} | {p.visitante for p in partidos})
        idx = {e: i for i, e in enumerate(self.equipos)}
        n = len(self.equipos)

        h = np.array([idx[p.local] for p in partidos])
        a = np.array([idx[p.visitante] for p in partidos])
        x = np.array([p.goles_local for p in partidos])
        y = np.array([p.goles_visitante for p in partidos])
        dias = np.array([(ref - p.fecha).days for p in partidos], dtype=float)
        peso = np.exp(-self.xi * np.maximum(dias, 0))

        def desempaquetar(theta):
            # El último ataque se deduce para que la media de ataques sea 0 (identificabilidad).
            att = np.append(theta[: n - 1], -np.sum(theta[: n - 1]))
            dfn = theta[n - 1 : 2 * n - 1]
            return att, dfn, theta[2 * n - 1], theta[2 * n]

        def neg_log_vero(theta):
            att, dfn, campo, rho = desempaquetar(theta)
            lam = np.exp(att[h] + dfn[a] + campo)
            mu = np.exp(att[a] + dfn[h])
            tau = np.ones_like(lam)
            m00 = (x == 0) & (y == 0)
            m01 = (x == 0) & (y == 1)
            m10 = (x == 1) & (y == 0)
            m11 = (x == 1) & (y == 1)
            tau[m00] = 1 - lam[m00] * mu[m00] * rho
            tau[m01] = 1 + lam[m01] * rho
            tau[m10] = 1 + mu[m10] * rho
            tau[m11] = 1 - rho
            tau = np.clip(tau, 1e-10, None)
            ll = (
                np.log(tau)
                + x * np.log(lam) - lam
                + y * np.log(mu) - mu
            )
            # Penalización suave para equipos con pocos partidos (evita fuerzas extremas)
            reg = 0.01 * (np.sum(att**2) + np.sum(dfn**2))
            return -np.sum(peso * ll) + reg

        theta0 = np.concatenate([np.zeros(n - 1), np.zeros(n), [0.25, -0.05]])
        limites = [(None, None)] * (2 * n - 1) + [(-1, 1), (-0.3, 0.3)]
        res = minimize(neg_log_vero, theta0, method="L-BFGS-B", bounds=limites)

        att, dfn, campo, rho = desempaquetar(res.x)
        self.ataque = dict(zip(self.equipos, att))
        self.defensa = dict(zip(self.equipos, dfn))
        self.campo, self.rho = float(campo), float(rho)
        self.ajustado = True
        return self

    def conoce(self, equipo: str) -> bool:
        return equipo in self.ataque

    # -------------------------------------------------------------- predicción
    def goles_esperados(self, local: str, visitante: str) -> tuple[float, float]:
        lam = np.exp(self.ataque[local] + self.defensa[visitante] + self.campo)
        mu = np.exp(self.ataque[visitante] + self.defensa[local])
        return float(lam), float(mu)

    def tabla_marcadores(self, local: str, visitante: str) -> np.ndarray:
        """Matriz M[i, j] = probabilidad de que acabe i (local) - j (visitante)."""
        lam, mu = self.goles_esperados(local, visitante)
        g = np.arange(MAX_GOLES + 1)
        m = np.outer(poisson.pmf(g, lam), poisson.pmf(g, mu))
        m[0, 0] *= 1 - lam * mu * self.rho
        m[0, 1] *= 1 + lam * self.rho
        m[1, 0] *= 1 + mu * self.rho
        m[1, 1] *= 1 - self.rho
        return m / m.sum()


def mercados(m: np.ndarray) -> dict[str, float]:
    """Convierte la tabla de marcadores en probabilidades de cada mercado de apuestas."""
    i, j = np.indices(m.shape)
    total = i + j
    p = {
        "Gana local (1)": m[i > j].sum(),
        "Empate (X)": m[i == j].sum(),
        "Gana visitante (2)": m[i < j].sum(),
    }
    p["Local o empate (1X)"] = p["Gana local (1)"] + p["Empate (X)"]
    p["Visitante o empate (X2)"] = p["Gana visitante (2)"] + p["Empate (X)"]
    p["No hay empate (12)"] = p["Gana local (1)"] + p["Gana visitante (2)"]
    for linea in (0.5, 1.5, 2.5, 3.5, 4.5):
        mas = m[total > linea].sum()
        p[f"Más de {linea} goles"] = mas
        p[f"Menos de {linea} goles"] = 1 - mas
    p["Ambos marcan: Sí"] = m[(i > 0) & (j > 0)].sum()
    p["Ambos marcan: No"] = 1 - p["Ambos marcan: Sí"]
    p["Local marca"] = m[i > 0].sum()
    p["Visitante marca"] = m[j > 0].sum()
    return {k: float(v) for k, v in p.items()}


def marcador_mas_probable(m: np.ndarray) -> tuple[str, float]:
    i, j = np.unravel_index(np.argmax(m), m.shape)
    return f"{i}-{j}", float(m[i, j])
