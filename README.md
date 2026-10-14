# Picks Dorados ⚽

App móvil con los partidos del día y la probabilidad de cada mercado (1X2, más/menos goles,
ambos marcan…). Los picks de ≥75% salen en dorado y los que superan a la cuota de la casa
llevan la etiqueta VALOR.

👉 **Para usarla solo con el móvil, sigue [GUIA-MOVIL.md](GUIA-MOVIL.md).**
Lo de abajo es para quien quiera ejecutarla en un ordenador.

## Qué hace cada archivo

| Archivo | Para qué sirve |
|---|---|
| `diario.py` | Lo que GitHub ejecuta cada mañana: calcula, genera la app y avisa a Telegram. |
| `web.py` + `plantilla.html` | Generan la app web (`python web.py --demo` para verla con datos de ejemplo). |
| `.github/workflows/actualizar.yml` | La programación automática en GitHub. |
| `bot.py` | Bot de Telegram interactivo (`/hoy`, `/partido N`) si lo tienes en un ordenador o servidor. |
| `modelo.py` | El "cerebro": modelo Dixon-Coles que calcula las probabilidades. |
| `analisis.py` | Mezcla modelo + cuotas, decide los dorados y escribe los mensajes. |
| `datos.py` | Descarga resultados y partidos de football-data.co.uk (gratis, sin registro). |
| `config.py` | Ligas, umbral del dorado, peso de las cuotas… Aquí se toca todo. |
| `backtest.py` | Comprueba con temporadas pasadas si los porcentajes se cumplen. |
| `demo.py` | Prueba sin internet ni Telegram, con una liga inventada. |

## Puesta en marcha (unos 15 minutos)

**1. Instala Python 3.10 o superior** desde python.org (en Windows marca "Add Python to PATH").

**2. Abre una terminal en esta carpeta e instala lo necesario:**
```
pip install -r requirements.txt
```

**3. Prueba que funciona sin internet:**
```
python demo.py
python tests.py
```

**4. Crea el bot en Telegram:**
- Habla con **@BotFather** → `/newbot` → elige nombre → te da un **token**.
- Crea un **canal** y añade el bot como **administrador**.

**5. Configura:** copia `.env.example` como `.env` y pega el token y el nombre del canal.

**6. Comprueba que el modelo acierta con datos reales:**
```
python backtest.py SP1
```
Mira la tabla de calibración: si en el tramo 80-90% el "Real" está cerca del "Predicho", vamos bien.

**7. Arranca el bot:**
```
python bot.py
```
Publica el resumen a la hora configurada y responde a `/hoy`, `/partido N` y `/ayuda`.
Para publicar en el momento: `python bot.py --ahora`.

## Dejarlo encendido 24 h

El bot tiene que estar corriendo para publicar y responder. Opciones:
- Tu ordenador encendido (para empezar).
- Un servidor pequeño (VPS de 4-5 €/mes: Hetzner, OVH, DigitalOcean…). Se sube la carpeta y
  se lanza con `nohup python bot.py &` o como servicio.

## Ajustes útiles (`config.py`)

- `UMBRAL_DORADO`: 0.75 por defecto. Súbelo a 0.80 para menos picks pero más seguros.
- `PESO_MERCADO`: cuánto se fía de las cuotas (0.5 = mitad modelo, mitad mercado).
  Las casas saben de lesiones y rotaciones; el modelo no. Bajarlo mucho empeora la precisión.
- `LIGAS`: añade o quita ligas (códigos de football-data.co.uk).
- `MERCADOS_TRIVIALES`: mercados que nunca se destacan porque casi siempre salen y pagan nada.

## Límites (léelo)

- El modelo solo ve resultados: no sabe de lesiones, sanciones ni rotaciones. Por eso se mezcla con las cuotas.
- Que un pick sea 🟡 no significa que sea buena apuesta: a cuota 1.10 hace falta acertar el 91%.
  Lo interesante es el 💎.
- football-data.co.uk actualiza `fixtures.csv` unas pocas veces por semana. Si un día faltan partidos,
  pon una clave gratuita de football-data.org en `.env` como respaldo.
- Equipos recién ascendidos sin historial se saltan hasta que acumulan partidos.
- En España la publicidad de apuestas está regulada (Real Decreto 958/2020). Si vas a monetizar
  con enlaces de afiliado de casas de apuestas, revísalo antes.
