"""Sondeo temporal de fuentes de datos para competiciones europeas."""
import requests


def probar(nombre, url, n=500):
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        print(f"### {nombre}: HTTP {r.status_code}, {len(r.content)} bytes")
        if r.ok:
            print("   ", r.text[:n].replace("\n", " | "))
        return r.text if r.ok else ""
    except Exception as e:
        print(f"### {nombre}: ERROR {str(e)[:150]}")
        return ""


probar("clubelo https", "https://api.clubelo.com/Fixtures", 300)
for liga in ("UEFA_Champions_League", "UEFA_Europa_League", "UEFA_Europa_Conference_League"):
    for d in ("2026-10-20", "2026-10-21", "2026-10-22"):
        t = probar(f"thesportsdb {liga} {d}",
                   f"https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d={d}&l={liga}", 250)
probar("thesportsdb CL next", "https://www.thesportsdb.com/api/v1/json/123/eventsnextleague.php?id=4480", 600)
probar("thesportsdb CL season", "https://www.thesportsdb.com/api/v1/json/123/eventsseason.php?id=4480&s=2026-2027", 400)
for temp in ("2024-25", "2023-24"):
    for comp in ("cl", "el", "conf"):
        probar(f"openfootball {temp} {comp}",
               f"https://raw.githubusercontent.com/openfootball/champions-league/master/{temp}/{comp}.txt", 120)
probar("openfootball repo listing", "https://api.github.com/repos/openfootball/champions-league/contents/2025-26", 600)
probar("fd new AUT", "https://www.football-data.co.uk/new/AUT.csv", 300)
probar("fd B1", "https://www.football-data.co.uk/mmz4281/2627/B1.csv", 200)
probar("fd T1", "https://www.football-data.co.uk/mmz4281/2627/T1.csv", 200)
probar("fd SC0", "https://www.football-data.co.uk/mmz4281/2627/SC0.csv", 200)
