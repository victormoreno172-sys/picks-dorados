"""
Cuotas de Winamax a través de The Odds API (https://the-odds-api.com).

Winamax no tiene API pública. The Odds API ofrece Winamax Francia (winamax_fr) y
Winamax Alemania (winamax_de); Winamax España no está, pero sus cuotas suelen
ser muy parecidas a las de Francia.

Plan gratuito: 500 créditos al mes. Cada petición de cuotas cuesta
(nº de mercados) créditos; consultar qué partidos hay es gratis. Por eso:
  - solo se piden cuotas de competiciones con partidos en los próximos 3 días,
  - cada competición se refresca como mucho una vez cada 20 horas,
  - el gasto diario se reparte con lo que queda de mes.
"""
from __future__ import annotations

import calendar
import difflib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config

URL = "https://api.the-odds-api.com/v4"
CASAS = "winamax_fr,winamax_de"  # se prefiere la francesa
CACHE = os.path.join(config.CARPETA_CACHE, "cuotas")
TZ = ZoneInfo(config.ZONA_HORARIA)

# Competición de The Odds API -> nuestro código
DEPORTES = {
    "soccer_spain_la_liga": "SP1", "soccer_spain_segunda_division": "SP2", "soccer_epl": "E0",
    "soccer_efl_champ": "E1", "soccer_italy_serie_a": "I1", "soccer_germany_bundesliga": "D1",
    "soccer_france_ligue_one": "F1", "soccer_netherlands_eredivisie": "N1",
    "soccer_portugal_primeira_liga": "P1", "soccer_usa_mls": "MLS", "soccer_argentina_primera_division": "ARG", "soccer_uefa_champs_league": "UCL",
    "soccer_uefa_europa_league": "UEL", "soccer_uefa_europa_conference_league": "UECL",
    "basketball_nba": "NBA", "basketball_euroleague": "EL",
}
MERCADOS_FUTBOL = "h2h,totals"
MERCADOS_BASKET = "h2h,spreads,totals"


@dataclass
class EventoCuotas:
    liga: str
    fecha: date
    local: str
    visitante: str
    casa: str = ""
    cuotas: dict[str, float] = field(default_factory=dict)  # nuestro nombre de mercado -> cuota
    spread_local: float | None = None  # línea de hándicap del local (negativa = favorito)
    total: float | None = None


# --------------------------------------------------------------- traducir
def _traducir(ev: dict, liga: str) -> EventoCuotas | None:
    casas = {b["key"]: b for b in ev.get("bookmakers", [])}
    b = casas.get("winamax_fr") or casas.get("winamax_de")
    if not b:
        return None
    dt = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).astimezone(TZ)
    basket = config.es_baloncesto(liga) or liga in ("ATP", "WTA")  # dos opciones: sin empate
    unidad = "puntos" if basket else "goles"
    e = EventoCuotas(liga, dt.date(), ev["home_team"], ev["away_team"],
                     "Winamax" + (" FR" if b["key"] == "winamax_fr" else " DE"))
    for m in b.get("markets", []):
        for o in m.get("outcomes", []):
            precio, nombre, punto = o.get("price"), o.get("name"), o.get("point")
            if not precio:
                continue
            lado = "local" if nombre == ev["home_team"] else "visitante" if nombre == ev["away_team"] else None
            if m["key"] == "h2h":
                if basket and lado:
                    e.cuotas[f"Gana {lado}"] = precio
                elif not basket:
                    clave = {"local": "Gana local (1)", "visitante": "Gana visitante (2)"}.get(lado)
                    if nombre == "Draw":
                        clave = "Empate (X)"
                    if clave:
                        e.cuotas[clave] = precio
            elif m["key"] == "totals" and punto is not None:
                pal = {"Over": "Más", "Under": "Menos"}.get(nombre)
                if pal:
                    e.cuotas[f"{pal} de {punto:g} {unidad}"] = precio
                    if e.total is None or nombre == "Over":
                        e.total = float(punto)
            elif m["key"] == "spreads" and punto is not None and lado:
                e.cuotas[f"Hándicap {lado} {punto:+g}"] = precio
                if lado == "local":
                    e.spread_local = float(punto)
    return e if e.cuotas else None


# --------------------------------------------------------------- descargar
def _get(ruta: str, **params):
    params["apiKey"] = config.ODDS_API_KEY
    r = requests.get(f"{URL}/{ruta}", params=params, timeout=40)
    restantes = r.headers.get("x-requests-remaining")
    if restantes is not None:
        _guardar_estado({"restantes": float(restantes), "fecha": time.time()})
    r.raise_for_status()
    return r.json()


def _estado() -> dict:
    try:
        with open(os.path.join(CACHE, "estado.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guardar_estado(e: dict):
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, "estado.json"), "w") as f:
        json.dump(e, f)


def obtener(hoy: date) -> list[EventoCuotas]:
    if not config.ODDS_API_KEY:
        print("  cuotas Winamax: sin clave ODDS_API_KEY (se usan las cuotas medias del mercado)")
        return []
    os.makedirs(CACHE, exist_ok=True)
    try:
        activos = {s["key"] for s in _get("sports")}  # gratis
    except requests.RequestException as e:
        print(f"  cuotas Winamax: no disponible ({e})")
        return []

    limite = datetime.now(TZ) + timedelta(days=3)
    candidatos = []
    # Torneos de tenis activos (cambian cada semana): solo el ganador, 1 crédito por torneo
    deportes = dict(DEPORTES)
    for clave in activos:
        if clave.startswith("tennis_atp"):
            deportes[clave] = "ATP"
        elif clave.startswith("tennis_wta"):
            deportes[clave] = "WTA"
    for clave, liga in deportes.items():
        if clave not in activos:
            continue
        ruta = os.path.join(CACHE, f"{clave}.json")
        fresco = os.path.exists(ruta) and time.time() - os.path.getmtime(ruta) < 20 * 3600
        if fresco:
            continue
        try:
            eventos = _get(f"sports/{clave}/events")  # gratis
        except requests.RequestException:
            continue
        pronto = sum(1 for ev in eventos
                     if datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")) <= limite)
        if pronto:
            candidatos.append((pronto, clave, liga))

    # Presupuesto: lo que queda de créditos repartido entre los días que quedan de mes
    restantes = _estado().get("restantes", 500)
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    quedan_dias = max(1, dias_mes - hoy.day + 1)
    presupuesto = max(0.0, (restantes - 10) / quedan_dias) * 2  # x2: este cupo cubre ~2 días (caché de 20 h)
    gastado = 0
    for pronto, clave, liga in sorted(candidatos, reverse=True):
        mercados = ("h2h" if liga in ("ATP", "WTA") else
                    MERCADOS_BASKET if config.es_baloncesto(liga) else MERCADOS_FUTBOL)
        coste = len(mercados.split(","))
        if gastado + coste > presupuesto:
            print(f"  cuotas Winamax: sin presupuesto hoy para {clave}")
            continue
        try:
            datos = _get(f"sports/{clave}/odds", bookmakers=CASAS, markets=mercados, oddsFormat="decimal")
            with open(os.path.join(CACHE, f"{clave}.json"), "w", encoding="utf-8") as f:
                json.dump(datos, f)
            gastado += coste
        except requests.RequestException as e:
            print(f"  cuotas Winamax: fallo en {clave} ({e})")
    print(f"  cuotas Winamax: {gastado} créditos gastados hoy, quedan ~{_estado().get('restantes', '?')}")
    sondear_mercados(activos)

    salida = []
    for clave, liga in deportes.items():
        ruta = os.path.join(CACHE, f"{clave}.json")
        if not os.path.exists(ruta) or time.time() - os.path.getmtime(ruta) > 72 * 3600:
            continue
        with open(ruta, encoding="utf-8") as f:
            for ev in json.load(f):
                e = _traducir(ev, liga)
                if e and e.fecha >= hoy - timedelta(days=1):
                    salida.append(e)
    print(f"  cuotas Winamax: {len(salida)} partidos con cuotas")
    return salida


def sondear_mercados(activos: set):
    """Una sola vez: qué mercados extra da Winamax por partido (para decidir si pagar el plan)."""
    marca = os.path.join(CACHE, "sondeo_mercados.txt")
    if os.path.exists(marca):
        with open(marca, encoding="utf-8") as f:
            print("  sondeo de mercados Winamax (guardado):", f.read()[:600])
        return
    extras = ("btts,draw_no_bet,double_chance,alternate_totals,alternate_spreads,team_totals,"
              "h2h_h1,totals_h1,spreads,alternate_totals_corners,alternate_totals_cards")
    resultado = []
    for clave in ("soccer_spain_la_liga", "soccer_epl", "soccer_uefa_champs_league", "basketball_nba"):
        if clave not in activos:
            continue
        try:
            eventos = _get(f"sports/{clave}/events")
            if not eventos:
                continue
            ev = eventos[0]
            mercados = extras if clave.startswith("soccer") else "alternate_spreads,alternate_totals,team_totals,player_points"
            d = _get(f"sports/{clave}/events/{ev['id']}/odds", bookmakers=CASAS, markets=mercados, oddsFormat="decimal")
            for b in d.get("bookmakers", []):
                resultado.append(f"{clave} {b['key']}: " + ", ".join(m["key"] for m in b.get("markets", [])))
            if not d.get("bookmakers"):
                resultado.append(f"{clave}: Winamax no da mercados extra")
        except requests.RequestException as e:
            resultado.append(f"{clave}: error {e}")
    texto = " | ".join(resultado) or "sin datos"
    with open(marca, "w", encoding="utf-8") as f:
        f.write(texto)
    print("  sondeo de mercados Winamax:", texto)


# ----------------------------------------------------------------- casar
# Mismo equipo escrito distinto en cada fuente (ya normalizado)
ALIAS_CUOTAS = {
    "lafc": "los angeles", "los angeles fc": "los angeles", "la galaxy": "los angeles galaxy",
    "red bull new york": "new york red bulls", "ny red bulls": "new york red bulls",
    "new york city": "new york city", "nycfc": "new york city", "st louis city": "st louis city",
    "dc united": "d c united", "inter miami": "inter miami", "cf montreal": "montreal",
}


def _norm(nombre: str) -> str:
    from europa import ALIAS, normalizar
    n = normalizar(nombre)
    n = ALIAS_CUOTAS.get(n, n)
    alias = ALIAS.get(n)
    return normalizar(alias) if alias else n


def _parecido(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and (ta <= tb or tb <= ta) and max(len(t) for t in ta & tb or {""}) >= 4:
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


class Cuotas:
    def __init__(self, eventos: list[EventoCuotas]):
        self.eventos = eventos
        self.usados = 0

    def buscar(self, liga: str, fecha: date, local: str, visitante: str) -> EventoCuotas | None:
        if liga in ("ATP", "WTA"):
            # En tenis no hay local: el orden de los jugadores puede venir al revés
            e = self._buscar(liga, fecha, local, visitante)
            if e:
                return e
            e = self._buscar(liga, fecha, visitante, local)
            if e:
                giro = {"Gana local": "Gana visitante", "Gana visitante": "Gana local"}
                return EventoCuotas(e.liga, e.fecha, e.visitante, e.local, e.casa,
                                    {giro.get(k, k): v for k, v in e.cuotas.items()})
            return None
        return self._buscar(liga, fecha, local, visitante)

    def _buscar(self, liga: str, fecha: date, local: str, visitante: str) -> EventoCuotas | None:
        mejor, puntos = None, 0.0
        for e in self.eventos:
            if e.liga != liga or abs((e.fecha - fecha).days) > 1:
                continue
            sl, sv = _parecido(local, e.local), _parecido(visitante, e.visitante)
            if min(sl, sv) >= 0.55 and sl + sv > puntos:
                mejor, puntos = e, sl + sv
        if mejor and puntos >= 1.3:
            self.usados += 1
            return mejor
        # Si un equipo coincide claramente y solo hay un partido así ese día, es ese
        claros = [e for e in self.eventos if e.liga == liga and abs((e.fecha - fecha).days) <= 1
                  and (_parecido(local, e.local) >= 0.9 or _parecido(visitante, e.visitante) >= 0.9)
                  and max(_parecido(local, e.local), _parecido(visitante, e.visitante)) >= 0.9]
        if len(claros) == 1:
            self.usados += 1
            return claros[0]
        return None


_INSTANCIA: Cuotas | None = None


def instancia(hoy: date) -> Cuotas:
    global _INSTANCIA
    if _INSTANCIA is None:
        try:
            _INSTANCIA = Cuotas(obtener(hoy))
        except Exception as e:  # las cuotas son un extra: nunca deben tumbar la app
            print(f"  cuotas Winamax: error inesperado ({e})")
            _INSTANCIA = Cuotas([])
    return _INSTANCIA
