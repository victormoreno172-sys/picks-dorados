"""Sondeo temporal de fuentes de datos para competiciones europeas."""
import json

import requests

B = "https://www.thesportsdb.com/api/v1/json/123/"


def js(url):
    try:
        r = requests.get(url, timeout=30)
        return r.json() if r.ok else {"_http": r.status_code}
    except Exception as e:
        return {"_err": str(e)[:100]}


ligas = js(B + "all_leagues.php").get("leagues") or []
print("ligas UEFA:", [(l["idLeague"], l["strLeague"]) for l in ligas if "UEFA" in l["strLeague"] or "Conference" in l["strLeague"]])
s = js(B + "search_all_leagues.php?c=Europe&s=Soccer")
print("busqueda europa:", str(s)[:600])

for lid in ("4480", "4481", "5071"):
    for d in ("2026-10-14", "2026-10-15"):
        ev = js(B + f"eventsday.php?d={d}&l={lid}").get("events") or []
        print(f"eventsday {lid} {d}: {len(ev)}", [(e['strHomeTeam'], e['strAwayTeam'], e.get('strTimestamp')) for e in ev][:20])
    ev = js(B + f"eventsnextleague.php?id={lid}").get("events") or []
    print(f"next {lid}: {len(ev)}", [(e['strHomeTeam'], e['strAwayTeam'], e.get('strTimestamp'), e.get('strLeague')) for e in ev][:5])
    ev = js(B + f"eventsround.php?id={lid}&r=3&s=2026-2027").get("events") or []
    print(f"round3 {lid}: {len(ev)}", [(e['strHomeTeam'], e['strAwayTeam'], e.get('strTimestamp')) for e in ev][:20])
    ev = js(B + f"eventsseason.php?id={lid}&s=2026-2027").get("events") or []
    print(f"season {lid}: {len(ev)}")
ev = js(B + "eventsday.php?d=2026-10-14&s=Soccer").get("events") or []
print("dia futbol:", len(ev), sorted({e.get('strLeague') for e in ev})[:40])
