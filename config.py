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


def nombre_liga(codigo: str) -> str:
    return (LIGAS.get(codigo) or EUROPA.get(codigo) or (codigo,))[0]

# --- Reglas de las predicciones --------------------------------------------
UMBRAL_DORADO = 0.75     # a partir de esta probabilidad el pick sale en dorado
UMBRAL_VALOR = 0.05      # 💎 si nuestra probabilidad supera a la de la cuota en 5 puntos
PESO_MERCADO = 0.5       # cuánto pesan las cuotas frente al modelo (0 = solo modelo)
TEMPORADAS_HISTORICO = 3  # temporadas que se usan para entrenar

# Mercados que casi siempre superan el umbral y pagan muy poco: no se destacan.
MERCADOS_TRIVIALES = {"Más de 0.5 goles", "Menos de 4.5 goles"}

CARPETA_CACHE = os.path.join(os.path.dirname(__file__), "cache")
