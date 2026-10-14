# Picks Dorados desde el móvil 📱

La app se actualiza sola cada mañana en GitHub (gratis) y tú la abres en el móvil como
cualquier otra app. No necesitas ordenador.

## 1. Crea tu cuenta y el repositorio (5 min)

1. Entra en **github.com** desde el navegador del móvil y crea una cuenta.
2. Toca **+ → New repository**.
   - Nombre: `picks-dorados`
   - Márcalo como **Public** (GitHub Pages gratis solo funciona con repositorios públicos).
   - Toca **Create repository**.
3. Dile a Claude el nombre de tu usuario de GitHub y yo subo todo el código.

## 2. Activa la web (1 min)

En tu repositorio: **Settings → Pages → Source** y elige **GitHub Actions**.

> Si no ves "Settings", abre el menú del navegador y activa **"Versión para ordenador"**.

## 3. Lánzalo por primera vez (1 min)

Pestaña **Actions → Actualizar picks → Run workflow**. Tarda 1-2 minutos.
Cuando salga el tic verde ✅, tu app estará en:

```
https://TU-USUARIO.github.io/picks-dorados/
```

A partir de ahí se actualiza sola dos veces al día (mañana y tarde).

## 4. Ponla en la pantalla de inicio

- **iPhone (Safari):** botón Compartir → **Añadir a pantalla de inicio**.
- **Android (Chrome):** menú ⋮ → **Añadir a pantalla de inicio** (o "Instalar app").

Se abre a pantalla completa, con su icono, como una app normal.

## 5. Opcional: canal de Telegram

Para que además publique el resumen cada mañana en un canal:

1. En Telegram, habla con **@BotFather** → `/newbot` → guarda el **token**.
2. Crea un canal y añade el bot como **administrador**.
3. En GitHub: **Settings → Secrets and variables → Actions → New repository secret**:
   - `TELEGRAM_TOKEN` → el token
   - `TELEGRAM_CANAL` → `@nombre_de_tu_canal`

## Cosas a saber

- **Qué cubre:** LaLiga, Segunda, Premier, Championship, Serie A, Bundesliga, Ligue 1, Eredivisie,
  Liga Portugal, y la **Champions, Europa League y Conference League**.
- **Competiciones europeas:** se calculan con un modelo de toda Europa (ligas nacionales + partidos
  europeos de las últimas temporadas), que aprende el nivel de cada liga. No llevan cuotas, así que
  no salen etiquetas VALOR en esos partidos.
- **Si un día sale vacía:** puede que no haya partidos de esas ligas (parones de selecciones)
  o que la fuente aún no los haya publicado. La app muestra también los próximos días con partidos.
- La clave gratuita de TheSportsDB (calendario europeo) a veces no trae todos los partidos de una
  jornada. Con una clave de pago suya (secreto `THESPORTSDB_KEY` en GitHub) salen todos.
- **Si falla la descarga de datos**, la app se queda con la última versión buena y GitHub te avisa por email.
- **GitHub pausa las tareas automáticas tras 60 días sin cambios en el repositorio.** Te manda un
  email; basta con entrar en Actions y tocar "Enable workflow".
- Cambiar el umbral del dorado, las ligas, etc.: archivo `config.py` (o pídemelo a mí).
- Las probabilidades son estimaciones, no certezas. Juega con responsabilidad (+18).
