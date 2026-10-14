"""Sondeo temporal: fuentes de datos de baloncesto."""
import json
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept": "application/json"}


def probar(nombre, url, n=500, headers=UA):
    try:
        r = requests.get(url, timeout=30, headers=headers)
        print(f"### {nombre}: HTTP {r.status_code}, {len(r.content)} bytes")
        if r.ok:
            print("   ", r.text[:n].replace("\n", " "))
        return r
    except Exception as e:
        print(f"### {nombre}: ERROR {str(e)[:150]}")


r = probar("nba schedule", "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json", 300)
if r is not None and r.ok:
    d = r.json()["leagueSchedule"]
    print("   temporada", d.get("seasonYear"), "fechas", len(d["gameDates"]))
    for gd in d["gameDates"]:
        if gd["gameDate"].startswith(("10/14/2026", "10/20/2026", "10/21/2026", "10/22/2026", "04/10/2026")):
            print("   ", gd["gameDate"], [(g["homeTeam"]["teamTricode"], g["awayTeam"]["teamTricode"], g.get("gameStatus"), g["homeTeam"].get("score")) for g in gd["games"]][:6])
probar("nba schedule 2025-26 archive", "https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/2025/league/00_full_schedule.json", 200)

for comp in ("E", "U"):
    for s in ("2026", "2025"):
        probar(f"euroleague feeds {comp}{s}",
               f"https://feeds.incrowdsports.com/provider/euroleague-feeds/v2/competitions/{comp}/seasons/{comp}{s}/games", 400)
    probar(f"euroleague api-live {comp}2026", f"https://api-live.euroleague.net/v2/competitions/{comp}/seasons/{comp}2026/games", 300)

probar("sofascore basket dia", "https://api.sofascore.com/api/v1/sport/basketball/scheduled-events/2026-10-14", 300)
probar("sofascore www", "https://www.sofascore.com/api/v1/sport/basketball/scheduled-events/2026-10-14", 300)
for lg in ("nba", "mens-college-basketball"):
    probar(f"espn {lg}", f"https://site.api.espn.com/apis/site/v2/sports/basketball/{lg}/scoreboard?dates=20261021", 300)
probar("espn leagues", "https://sports.core.api.espn.com/v2/sports/basketball/leagues?limit=100", 1500)

B = "https://www.thesportsdb.com/api/v1/json/123/"
r = probar("tsdb ligas basket", B + "search_all_leagues.php?s=Basketball", 0)
if r is not None and r.ok:
    ligas = (r.json().get("countries") or [])
    print("   ", len(ligas), [(l["idLeague"], l["strLeague"], l.get("strCountry")) for l in ligas][:120])
for lid in ("4387", "4546", "4408", "4432", "4433", "4434", "4580"):
    r = probar(f"tsdb past {lid}", B + f"eventspastleague.php?id={lid}", 0)
    if r is not None and r.ok:
        ev = r.json().get("events") or []
        print("   ", len(ev), [(e.get("strLeague"), e.get("dateEvent"), e["strHomeTeam"], e["strAwayTeam"], e.get("intHomeScore"), e.get("intAwayScore")) for e in ev][:3])
    time.sleep(2.1)
    r = probar(f"tsdb season {lid}", B + f"eventsseason.php?id={lid}&s=2025-2026", 0)
    if r is not None and r.ok:
        ev = r.json().get("events") or []
        print("   ", len(ev))
    time.sleep(2.1)
