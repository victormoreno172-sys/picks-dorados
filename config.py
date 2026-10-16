"""Configuración. Lo sensible (token de Telegram) va en el archivo .env, no aquí."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
# Canal o chat donde se publica el resumen diario (ej: @mi_canal o -100123456789)
TELEGRAM_CANAL = os.getenv("TELEGRAM_CANAL", "")
HORA_PUBLICACION = os.getenv("HORA_PUBLICACION", "09:00")  # hora de Madrid
ZONA_HORARIA = "Europe/Madrid"

# --- Fuente opcional de partidos (si fixtures.csv no trae los del día) -------
FOOTBALL_DATA_ORG_KEY = os.getenv("FOOTBALL_DATA_ORG_KEY", "")

# --- Ligas ------------------------------------------------------------------
# código football-data.co.uk -> (nombre, código football-data.org)
LIGAS = {
    "SP1": ("🇪🇸 LaLiga", "PD"),
    "SP2": ("🇪🇸 Segunda División", None),
    "E0": ("🏴 Premier League", "PL"),
    "E1": ("🏴 Championship", "ELC"),
    "I1": ("🇮🇹 Serie A", "SA"),
    "D1": ("🇩🇪 Bundesliga", "BL1"),
    "F1": ("🇫🇷 Ligue 1", "FL1"),
    "N1": ("🇳🇱 Eredivisie", "DED"),
    "P1": ("🇵🇹 Liga Portugal", "PPL"),
}

# Ligas que se leen de ESPN: código -> (nombre, identificador de ESPN)
LIGAS_ESPN = {
    "MLS": ("🇺🇸 MLS", "usa.1"),
    "ARG": ("🇦🇷 Liga Argentina", "arg.1"),
}

# --- Competiciones europeas (calendario de TheSportsDB) ---------------------
# código -> (nombre, id de TheSportsDB)
EUROPA = {
    "UCL": ("🏆 Champions League", "4480"),
    "UEL": ("🏆 Europa League", "4481"),
    "UECL": ("🏆 Conference League", "5071"),
}
# La clave pública "123" es gratis pero limita resultados. Con una clave de pago
# (patreon de TheSportsDB) se ven todas las jornadas completas.
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY", "")

# Cuotas de Winamax vía The Odds API (clave gratuita en https://the-odds-api.com)
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")


# --- Baloncesto -------------------------------------------------------------
# código -> (nombre, id de TheSportsDB). La NBA va aparte (datos oficiales + ESPN).
BASKET_EUROPA = {
    "EL": ("🏆 Euroliga", "4546"),
    "EC": ("🏆 Eurocup", "4547"),
    "BCL": ("🏆 Basketball Champions League", "4548"),
    "ACB": ("🇪🇸 Liga ACB", "4408"),
    "LBA": ("🇮🇹 Lega Basket", "4433"),
    "BBL": ("🇩🇪 BBL", "4441"),
    "LNB": ("🇫🇷 LNB Élite", "4423"),
    "BSL": ("🇹🇷 Süper Lig", "4475"),
    "GBL": ("🇬🇷 Greek Basket League", "4452"),
    "ABA": ("🌍 Liga ABA", "4477"),
    "LKL": ("🇱🇹 LKL", "4478"),
}
BASKET = {"NBA": ("🏀 NBA", None), "NBA-PRE": ("🏀 NBA · Pretemporada", None), **BASKET_EUROPA}


# Estados de TheSportsDB que significan "terminado"
ESTADOS_FIN = {"FT", "MATCH FINISHED", "FINISHED", "AET", "AP", "PEN", "AOT", "AFTER OVER TIME", "FINAL",
               "AFTER EXTRA TIME", "AFTER PENALTIES", "ENDED"}


def partido_terminado(estado: str | None, fecha, hoy) -> bool:
    """Terminado si la fuente lo dice, o si no dice nada y el día ya pasó (los 0-0 de partidos en juego no cuentan)."""
    e = (estado or "").strip().upper()
    if e in ESTADOS_FIN:
        return True
    return e == "" and fecha < hoy


def es_baloncesto(codigo: str) -> bool:
    return codigo in BASKET


def nombre_liga(codigo: str) -> str:
    return (LIGAS.get(codigo) or LIGAS_ESPN.get(codigo) or EUROPA.get(codigo) or BASKET.get(codigo)
            or (codigo,))[0]

# --- Reglas de las predicciones --------------------------------------------
UMBRAL_DORADO = 0.75     # a partir de esta probabilidad el pick sale en dorado
USAR_ROJO = False        # el rojo se quitó de la app
UMBRAL_ROJO_PROB = 0.70  # rojo: probabilidad al menos del 70%...
UMBRAL_ROJO_CUOTA = 1.40  # ...y cuota real de la casa al menos de 1.40
UMBRAL_VALOR = 0.05     # VALOR: la cuota real paga al menos un 5% más de lo que vale (prob × cuota − 1 ≥ 5%)
# Cuánto pesan las cuotas de la casa frente al modelo cuando las hay (0 = solo modelo).
# La auditoría (2.000+ partidos de 6 ligas simulados) dio lo mejor entre 0.7 y 1.0: las casas
# saben de lesiones, alineaciones, etc. En esports el modelo coincide mucho con la casa: 0.7.
PESO_MERCADO = 0.85
PESO_MERCADO_ESPORTS = 0.7
TEMPORADAS_HISTORICO = 3  # temporadas que se usan para entrenar

# Mercados que casi siempre superan el umbral y pagan muy poco: no se destacan.
MERCADOS_TRIVIALES = {"Más de 0.5 goles", "Menos de 4.5 goles"}

CARPETA_CACHE = os.path.join(os.path.dirname(__file__), "cache")
