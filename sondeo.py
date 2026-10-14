"""Sondeo temporal de fuentes de datos para competiciones europeas."""
import csv
import io
from collections import Counter

import requests


def probar(nombre, url, n=600):
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        print(f"### {nombre}: HTTP {r.status_code}, {len(r.content)} bytes")
        return r.text if r.ok else ""
    except Exception as e:
        print(f"### {nombre}: ERROR {e}")
        return ""


t = probar("clubelo fixtures", "http://api.clubelo.com/Fixtures")
if t:
    filas = list(csv.DictReader(io.StringIO(t)))
    print("cabecera:", list(filas[0].keys())[:20], "...", len(filas[0]))
    print("paises:", Counter(f["Country"] for f in filas).most_common(40))
    print("fechas:", sorted(Counter(f["Date"] for f in filas).items())[:15])
    for f in filas:
        if f["Country"] in ("EUR", "INT", "UEFA", "CL", "EL"):
            print("  euro:", f["Date"], f["Home"], f["Away"])
    for f in filas[:3]:
        print("  ej:", {k: f[k] for k in list(f)[:8]}, f.get("R:1-0"), f.get("R:2-1"))

for temp in ("2026-27", "2025-26"):
    for comp in ("cl", "el", "conf"):
        t = probar(f"openfootball {temp} {comp}",
                   f"https://raw.githubusercontent.com/openfootball/champions-league/master/{temp}/{comp}.txt")
        if t:
            print(t[:300].replace("\n", " | "))

t = probar("clubelo ranking", "http://api.clubelo.com/2026-10-14")
if t:
    print(t[:300])
