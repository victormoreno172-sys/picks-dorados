"""Icono y pantalla de inicio de la app: el logo pixel de Clávala (lo dibuja ../logo.py)."""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import logo  # noqa: E402

os.makedirs("assets", exist_ok=True)
logo.imagen(1024).convert("RGB").save("assets/icon-only.png")
# Icono adaptable de Android: el dibujo va dentro de la zona segura (~66 % central)
logo.imagen(1024, fondo=False, escala=0.62).save("assets/icon-foreground.png")
fondo = Image.new("RGB", (1024, 1024), logo.NOCHE2)
fondo.save("assets/icon-background.png")
sp = logo.pantalla_inicio()
sp.save("assets/splash.png")
sp.save("assets/splash-dark.png")
print("iconos listos")
