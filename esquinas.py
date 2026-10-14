"""
Córners y tarjetas (ligas con datos de football-data.co.uk: HC/AC, HY/AY, HR/AR).

Para cada estadística (córners, tarjetas) cada equipo tiene:
  - "a favor": cuántos saca / cuántas ve más que la media,
  - "en contra": cuántos concede / cuántas provoca al rival,
y hay un factor de jugar en casa. Es un modelo de Poisson con regularización
(como el de goles), pero los córners y las tarjetas varían más que los goles,
así que el total se calcula con una binomial negativa con la dispersión real
medida en los partidos.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

import numpy as np
from scipy.optimize import minimize
from scipy.stats import nbinom, poisson

import config
import datos
from analisis import Pick

LINEAS_CORNERS = (8.5, 9.5, 10.5, 11.5)
LINEAS_TARJETAS = (2.5, 3.5, 4.5, 5.5)


@dataclass
class Fila:
    fecha: date
    local: str
    visitante: str
    cl: int
    cv: int
    tl: int
    tv: int


def historico(liga: str, hoy: date) -> list[Fila]:
    out = []
    inicio = int(datos.codigo_temporada(hoy)[:2])
    for k in range(config.TEMPORADAS_HISTORICO):
        a = (inicio - k) % 100
        temp = f"{a:02d}{(a + 1) % 100:02d}"
        try:
            texto = datos._descargar(datos.URL_RESULTADOS.format(temp=temp, liga=liga), f"{liga}_{temp}.csv",
                                     6 if k == 0 else 24 * 30)
        except Exception:
            continue
        for f in csv.DictReader(io.StringIO(texto)):
            try:
                if not f.get("HomeTeam") or f.get("HC") in (None, "") or f.get("HY") in (None, ""):
                    continue
                rojas_l = int(float(f.get("HR") or 0))
                rojas_v = int(float(f.get("AR") or 0))
                out.append(Fila(datos._fecha(f["Date"]), f["HomeTeam"].strip(), f["AwayTeam"].strip(),
                                int(float(f["HC"])), int(float(f["AC"])),
                                int(float(f["HY"])) + rojas_l, int(float(f["AY"])) + rojas_v))
            except (ValueError, KeyError):
                continue
    return out


class ModeloConteo:
    def __init__(self, nombre: str, xi: float = 0.0025, reg: float = 4.0):
        self.nombre, self.xi, self.reg = nombre, xi, reg

    def ajustar(self, filas: list[Fila], hasta: date, campo: str) -> "ModeloConteo":
        fs = [f for f in filas if f.fecha < hasta]
        if len(fs) < 150:
            raise ValueError("pocos datos")
        eq = sorted({f.local for f in fs} | {f.visitante for f in fs})
        idx = {e: i for i, e in enumerate(eq)}
        n = len(eq)
        h = np.array([idx[f.local] for f in fs])
        a = np.array([idx[f.visitante] for f in fs])
        x = np.array([getattr(f, campo + "l") for f in fs], float)
        y = np.array([getattr(f, campo + "v") for f in fs], float)
        w = np.exp(-self.xi * np.array([(hasta - f.fecha).days for f in fs], float))

        def fun(t):
            fa, en = t[:n], t[n:2 * n]
            c0, ca = t[2 * n:]
            ll = c0 + ca + fa[h] + en[a]
            lm = c0 + fa[a] + en[h]
            lam, mu = np.exp(ll), np.exp(lm)
            nll = -np.sum(w * (x * ll - lam + y * lm - mu)) + self.reg * (fa @ fa + en @ en)
            r1, r2 = w * (x - lam), w * (y - mu)
            g_fa = -(np.bincount(h, r1, n) + np.bincount(a, r2, n)) + 2 * self.reg * fa
            g_en = -(np.bincount(a, r1, n) + np.bincount(h, r2, n)) + 2 * self.reg * en
            return nll, np.concatenate([g_fa, g_en, [-(r1.sum() + r2.sum()), -r1.sum()]])

        t0 = np.zeros(2 * n + 2)
        t0[2 * n] = np.log(max(0.5, (x.mean() + y.mean()) / 2))
        res = minimize(fun, t0, jac=True, method="L-BFGS-B")
        t = res.x
        self.favor = dict(zip(eq, t[:n]))
        self.contra = dict(zip(eq, t[n:2 * n]))
        self.c0, self.casa = t[2 * n:]
        # Dispersión del total (varianza / media) con los residuos ponderados
        lam = np.exp(self.c0 + self.casa + t[:n][h] + t[n:2 * n][a])
        mu = np.exp(self.c0 + t[:n][a] + t[n:2 * n][h])
        tot, media = x + y, lam + mu
        self.dispersion = float(max(1.0, np.sum(w * (tot - media) ** 2 / media) / w.sum()))
        self.media_liga = float(np.average(tot, weights=w))
        return self

    def conoce(self, e: str) -> bool:
        return e in self.favor

    def esperado(self, local: str, visitante: str) -> tuple[float, float]:
        lam = np.exp(self.c0 + self.casa + self.favor[local] + self.contra[visitante])
        mu = np.exp(self.c0 + self.favor[visitante] + self.contra[local])
        return float(lam), float(mu)

    def p_mas(self, total_medio: float, linea: float) -> float:
        k = int(np.floor(linea))
        if self.dispersion <= 1.02:
            return float(poisson.sf(k, total_medio))
        r = total_medio / (self.dispersion - 1)
        p = r / (r + total_medio)
        return float(nbinom.sf(k, r, p))


class Esquinas:
    """Modelos de córners y tarjetas por liga (se entrenan al pedirlos)."""

    def __init__(self, hoy: date):
        self.hoy = hoy
        self.modelos: dict[str, tuple[ModeloConteo, ModeloConteo] | None] = {}

    def _modelos(self, liga: str):
        if liga not in self.modelos:
            try:
                filas = historico(liga, self.hoy)
                mc = ModeloConteo("córners").ajustar(filas, self.hoy, "c")
                mt = ModeloConteo("tarjetas").ajustar(filas, self.hoy, "t")
                print(f"  córners/tarjetas {liga}: {len(filas)} partidos, media {mc.media_liga:.1f} córners "
                      f"(dispersión {mc.dispersion:.2f}), {mt.media_liga:.1f} tarjetas ({mt.dispersion:.2f})")
                self.modelos[liga] = (mc, mt)
            except Exception as e:
                print(f"  córners/tarjetas {liga}: sin datos ({e})")
                self.modelos[liga] = None
        return self.modelos[liga]

    def picks(self, liga: str, local: str, visitante: str) -> list[Pick]:
        m = self._modelos(liga)
        if not m:
            return []
        mc, mt = m
        out = []
        if mc.conoce(local) and mc.conoce(visitante):
            cl, cv = mc.esperado(local, visitante)
            for lin in LINEAS_CORNERS:
                p = mc.p_mas(cl + cv, lin)
                out += [Pick(f"Más de {lin:g} córners", p), Pick(f"Menos de {lin:g} córners", 1 - p)]
        if mt.conoce(local) and mt.conoce(visitante):
            tl, tv = mt.esperado(local, visitante)
            for lin in LINEAS_TARJETAS:
                p = mt.p_mas(tl + tv, lin)
                out += [Pick(f"Más de {lin:g} tarjetas", p), Pick(f"Menos de {lin:g} tarjetas", 1 - p)]
        return out
