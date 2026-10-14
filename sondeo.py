"""Sondeo temporal: fuentes de tenis."""
import io
import json
import os

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def probar(nombre, url, n=500, **kw):
    try:
        r = requests.get(url, timeout=40, headers=UA, **kw)
        print(f"### {nombre}: HTTP {r.status_code}, {len(r.content)} bytes, {r.headers.get('content-type')}")
        if r.ok and "json" in (r.headers.get("content-type") or ""):
            print("   ", r.text[:n].replace("\n", " "))
        return r
    except Exception as e:
        print(f"### {nombre}: ERROR {str(e)[:150]}")


for url in ("http://www.tennis-data.co.uk/2026/2026.xlsx", "http://www.tennis-data.co.uk/2026w/2026.xlsx",
            "http://www.tennis-data.co.uk/2025/2025.xlsx", "https://www.tennis-data.co.uk/2026/2026.xlsx"):
    r = probar("tennis-data " + url, url)
    if r is not None and r.ok and len(r.content) > 10000:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
            ws = wb.active
            filas = list(ws.iter_rows(values_only=True))
            print("    columnas:", filas[0])
            print("    primera:", filas[1])
            print("    última:", filas[-1], "total", len(filas))
        except Exception as e:
            print("    no se pudo leer:", e)

for lg in ("atp", "wta"):
    r = probar(f"espn {lg}", f"https://site.api.espn.com/apis/site/v2/sports/tennis/{lg}/scoreboard", 0)
    if r is not None and r.ok:
        d = r.json()
        evs = d.get("events", [])
        print("   eventos:", len(evs), [e.get("name") for e in evs][:8])
        if evs:
            e = evs[0]
            print("   claves evento:", list(e.keys()))
            grupos = e.get("groupings") or []
            print("   groupings:", len(grupos), [g.get("grouping", {}).get("displayName") for g in grupos][:6])
            comps = (grupos[0].get("competitions") if grupos else e.get("competitions")) or []
            print("   partidos en el primer grupo:", len(comps))
            if comps:
                c = comps[0]
                print("   ejemplo:", json.dumps({k: c.get(k) for k in ("date", "status", "round", "format", "venue")})[:500])
                print("   jugadores:", [(x.get("athlete", {}).get("displayName"), x.get("winner"), [l.get("value") for l in x.get("linescores", [])]) for x in c.get("competitors", [])])
    r = probar(f"espn {lg} fecha", f"https://site.api.espn.com/apis/site/v2/sports/tennis/{lg}/scoreboard?dates=20261016", 0)

key = os.getenv("ODDS_API_KEY")
if key:
    r = requests.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": key}, timeout=30)
    print("odds api deportes de tenis:", [(s["key"], s["title"]) for s in r.json() if s["key"].startswith("tennis")])
