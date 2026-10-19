"""Icono y pantalla de inicio de la app (se dibujan aquí para no depender de diseños externos)."""
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONDO, ORO, ORO2 = (7, 17, 12), (242, 191, 62), (255, 220, 120)
os.makedirs("assets", exist_ok=True)


def fuente(t):
    for f in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, t)
        except OSError:
            pass
    return ImageFont.load_default()


def emblema(S, fondo=True, escala=1.0):
    """Anillo dorado como un marcador de probabilidad (al 75 %) con un % en el centro."""
    k = 4  # se dibuja a 4x y se reduce: bordes suaves
    W = S * k
    im = Image.new("RGBA", (W, W), FONDO + (255,) if fondo else (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if fondo:  # degradado suave hacia el centro
        for i in range(60, 0, -1):
            r = W * 0.75 * i / 60
            c = tuple(int(FONDO[j] + (24 - FONDO[j] * 0.3) * (1 - i / 60)) for j in range(3))
            d.ellipse((W / 2 - r, W / 2 - r, W / 2 + r, W / 2 + r), fill=c + (255,))
    R = W * 0.33 * escala
    g = W * 0.06 * escala
    caja = (W / 2 - R, W / 2 - R, W / 2 + R, W / 2 + R)
    d.arc(caja, 0, 360, fill=(38, 52, 44, 255), width=int(g))
    d.arc(caja, -90, 180, fill=ORO + (255,), width=int(g))  # 75 % del anillo
    # punto brillante al final del arco
    a = math.radians(180)
    px, py = W / 2 + R * math.cos(a) - 0, W / 2 + R * math.sin(a)
    rr = g * 0.62
    d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=ORO2 + (255,))
    f = fuente(int(W * 0.30 * escala))
    d.text((W / 2, W / 2 + W * 0.01), "%", fill=ORO + (255,), font=f, anchor="mm")
    return im.resize((S, S), Image.LANCZOS)


emblema(1024).convert("RGB").save("assets/icon-only.png")
emblema(1024, fondo=False, escala=0.72).save("assets/icon-foreground.png")
Image.new("RGB", (1024, 1024), FONDO).save("assets/icon-background.png")

# Pantalla de inicio: emblema + nombre
S = 2732
sp = Image.new("RGB", (S, S), FONDO)
e = emblema(900, fondo=False)
sp.paste(e, ((S - 900) // 2, (S - 900) // 2 - 180), e)
d = ImageDraw.Draw(sp)
d.text((S / 2, S / 2 + 420), "PICKS DORADOS", fill=ORO, font=fuente(150), anchor="mm")
d.text((S / 2, S / 2 + 580), "Partidos · Probabilidades · Bot", fill=(138, 153, 178), font=fuente(70), anchor="mm")
sp.save("assets/splash.png")
sp.save("assets/splash-dark.png")
print("iconos listos")
