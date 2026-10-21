"""Logo de Clávala en pixel art (Temporada 0 · Pixel): una «C» dorada con el balón dentro.

Se dibuja en una rejilla de 32×32 píxeles y se amplía sin suavizar (bordes nítidos de videojuego).
Lo usan la web (icono y favicon) y la app Android (icono y pantalla de inicio).
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

N = 32
NOCHE, NOCHE2 = (11, 18, 32), (22, 33, 62)
ORO_CLARO, ORO, NARANJA, SOMBRA = (255, 209, 102), (255, 183, 3), (251, 133, 0), (122, 56, 0)
BLANCO, NEGRO = (255, 241, 232), (24, 30, 50)


def _balon(n: int) -> list[list[bool]]:
    """Balón de n×n píxeles (True = parche negro); se dibuja grande y se reduce."""
    S = 220
    im = Image.new("L", (S, S), 255)
    d = ImageDraw.Draw(im)
    c, r = S / 2, S / 2 - 2
    pent = lambda cx, cy, rr, rot: [(cx + rr * math.cos(math.radians(rot + 72 * i)), cy + rr * math.sin(math.radians(rot + 72 * i))) for i in range(5)]
    d.polygon(pent(c, c, r * 0.36, -90), fill=0)
    for i in range(5):
        a = math.radians(-90 + 72 * i + 36)
        d.polygon(pent(c + r * 0.98 * math.cos(a), c + r * 0.98 * math.sin(a), r * 0.36, -90 + 72 * i + 36), fill=0)
    pq = im.resize((n, n), Image.BOX)
    return [[pq.getpixel((x, y)) < 128 for x in range(n)] for y in range(n)]


BALON = [
    "....#####....",
    "..##KwwwK##..",
    ".#KKwwwwwKK#.",
    ".#wwwwKwwww#.",
    "#wwwwKKKwwww#",
    "#KwwKKKKKwwK#",
    "#KKwwKKKwwKK#",
    "#KwwwwwwwwwK#",
    "#wwwwwwwwwww#",
    ".#wwwwwwwww#.",
    ".#wwwKKKwww#.",
    "..##wKKKw##..",
    "....#####....",
]
GRIS = (196, 200, 220)
BORDE = (58, 68, 104)


def rejilla() -> list[list[tuple | None]]:
    g: list[list[tuple | None]] = [[None] * N for _ in range(N)]
    cx = cy = 15.5
    # La «C»: anillo grueso abierto a la derecha. Brillo en el borde exterior de arriba-izquierda,
    # naranja en el borde interior de abajo-derecha y contorno oscuro para que destaque en pequeño.
    dentro = set()
    for y in range(N):
        for x in range(N):
            dx, dy = x - cx, y - cy
            dist, ang = math.hypot(dx, dy), math.degrees(math.atan2(dy, dx))
            if 8.4 <= dist <= 13.6 and not (-38 <= ang <= 38):
                dentro.add((x, y))
                luz = (-dx - dy) / (dist * 1.414)
                c = ORO
                if dist >= 11.9 and luz > -0.1:
                    c = ORO_CLARO
                if dist <= 10.0 and luz < 0.2:
                    c = NARANJA
                if dist >= 12.4 and luz < -0.35:
                    c = NARANJA
                g[y][x] = c
    for (x, y) in list(dentro):   # contorno de 1 px
        for vx, vy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (x + vx, y + vy)
            if 0 <= p[0] < N and 0 <= p[1] < N and p not in dentro and g[p[1]][p[0]] is None:
                g[p[1]][p[0]] = SOMBRA
    # Balón dibujado a mano, centrado
    ox = oy = 9
    for j, fila in enumerate(BALON):
        for i, ch in enumerate(fila):
            if ch == "#":
                g[oy + j][ox + i] = BORDE
            elif ch == "K":
                g[oy + j][ox + i] = NEGRO
            elif ch == "w":
                g[oy + j][ox + i] = GRIS if (i + j) > 15 else BLANCO
    return g


def imagen(lado: int = 1024, fondo: bool = True, escala: float = 1.0) -> Image.Image:
    """Icono de lado×lado. fondo=False: transparente (para el icono adaptable de Android)."""
    g = rejilla()
    peq = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    for y in range(N):
        for x in range(N):
            if g[y][x]:
                peq.putpixel((x, y), g[y][x] + (255,))
    tam = int(lado * escala) // N * N
    dib = peq.resize((tam, tam), Image.NEAREST)
    out = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    if fondo:
        d = ImageDraw.Draw(out)
        for i in range(lado):   # degradado de arriba (más claro) a abajo
            t = i / lado
            d.line([(0, i), (lado, i)], fill=tuple(int(NOCHE2[j] * (1 - t) + NOCHE[j] * t) for j in range(3)) + (255,))
    out.alpha_composite(dib, ((lado - tam) // 2, (lado - tam) // 2))
    return out


def svg() -> str:
    """El mismo icono en SVG (un rectángulo por píxel, bordes nítidos a cualquier tamaño)."""
    g = rejilla()
    hx = lambda c: "#%02x%02x%02x" % c
    r = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" shape-rendering="crispEdges">',
         '<defs><linearGradient id="f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient></defs>' % (hx(NOCHE2), hx(NOCHE)),
         '<rect width="32" height="32" fill="url(#f)"/>']
    for y in range(N):
        x = 0
        while x < N:   # junta píxeles seguidos del mismo color en una fila
            c = g[y][x]
            if not c:
                x += 1
                continue
            x2 = x
            while x2 + 1 < N and g[y][x2 + 1] == c:
                x2 += 1
            r.append('<rect x="%d" y="%d" width="%d" height="1" fill="%s"/>' % (x, y, x2 - x + 1, hx(c)))
            x = x2 + 1
    r.append("</svg>")
    return "".join(r)


# Letras de 5×5 para escribir CLÁVALA en pixel (pantalla de inicio)
LETRAS = {"C": ["XXXX", "X...", "X...", "X...", "XXXX"], "L": ["X...", "X...", "X...", "X...", "XXXX"],
          "A": [".XX.", "X..X", "XXXX", "X..X", "X..X"], "Á": [".XX.", "X..X", "XXXX", "X..X", "X..X"], "V": ["X..X", "X..X", "X..X", ".XX.", ".XX."]}


def texto(t: str, px: int, color=ORO) -> Image.Image:
    w = sum(5 for _ in t) * px
    im = Image.new("RGBA", (w, 8 * px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 0
    for ch in t:
        for j, fila in enumerate(LETRAS[ch]):
            for i, v in enumerate(fila):
                if v == "X":
                    d.rectangle((x + i * px + px // 3, (j + 2) * px + px // 3, x + (i + 1) * px - 1 + px // 3, (j + 3) * px - 1 + px // 3), fill=SOMBRA)
                    d.rectangle((x + i * px, (j + 2) * px, x + (i + 1) * px - 1, (j + 3) * px - 1), fill=color)
        if ch == "Á":   # tilde
            d.rectangle((x + 2 * px, 0, x + 3 * px - 1, px - 1), fill=color)
        x += 5 * px
    return im


def pantalla_inicio(lado: int = 2732) -> Image.Image:
    """Splash: fondo noche, el logo y el nombre en letras pixel."""
    sp = Image.new("RGBA", (lado, lado), NOCHE + (255,))
    ic = imagen(896, fondo=False)
    sp.alpha_composite(ic, ((lado - 896) // 2, lado // 2 - 640))
    t = texto("CLÁVALA", 40)
    sp.alpha_composite(t, ((lado - t.width) // 2, lado // 2 + 300))
    return sp.convert("RGB")


if __name__ == "__main__":
    imagen(512).save("logo_prueba.png")
