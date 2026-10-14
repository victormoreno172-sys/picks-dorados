"""Sondeo temporal: ligas europeas de baloncesto en TheSportsDB y otras."""
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
B = "https://www.thesportsdb.com/api/v1/json/123/"


def js(url):
    try:
        r = requests.get(url, timeout=30, headers=UA)
        return r.json() if r.ok else {"_http": r.status_code}
    except Exception as e:
        return {"_err": str(e)[:100]}


for pais in ("Spain", "Italy", "Germany", "France", "Turkey", "Greece", "Europe", "World", "Lithuania", "Serbia", "Israel"):
    d = js(B + f"search_all_leagues.php?c={pais}&s=Basketball")
    print(pais, [(l["idLeague"], l["strLeague"]) for l in (d.get("countries") or [])])
    time.sleep(2.1)

for lid in ("4408", "4433"):
    for s in ("2025-2026", "2026-2027"):
        for r in (1, 2, 10, 30):
            ev = js(B + f"eventsround.php?id={lid}&r={r}&s={s}").get("events") or []
            print(f"round {lid} {s} r={r}: {len(ev)}", [(e.get("dateEvent"), e["strHomeTeam"], e["strAwayTeam"], e.get("intHomeScore")) for e in ev][:3])
            time.sleep(2.1)

r = requests.get("https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/2026/league/00_full_schedule.json", timeout=60, headers=UA)
print("nba 2026 full schedule:", r.status_code, len(r.content))
if r.ok:
    meses = r.json()["lscd"]
    n = sum(len(m["mscd"]["g"]) for m in meses)
    print("  partidos:", n, "ejemplo:", meses[0]["mscd"]["g"][0])
r = requests.get("https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/2025/league/00_full_schedule.json", timeout=60, headers=UA)
g = r.json()["lscd"][0]["mscd"]["g"][0]
print("nba 2025 ejemplo:", {k: g[k] for k in list(g)[:20]})

d = js("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261021")
for e in (d.get("events") or [])[:2]:
    c = e["competitions"][0]
    print("espn:", e["date"], [(t["homeAway"], t["team"]["displayName"], t.get("score")) for t in c["competitors"]],
          c.get("odds", [{}])[0].get("details") if c.get("odds") else None, c.get("odds", [{}])[0].get("overUnder") if c.get("odds") else None)
d = js("https://site.api.espn.com/apis/site/v2/sports/basketball/fiba/scoreboard")
print("espn fiba:", str(d)[:300])

g = js("https://feeds.incrowdsports.com/provider/euroleague-feeds/v2/competitions/E/seasons/E2026/games")["data"][0]
print("euroleague juego:", {k: g[k] for k in g if k in ("date", "utcDate", "local", "road", "played", "round", "phaseType")})
