import json, requests
UA = {"User-Agent": "Mozilla/5.0"}
def g(u, **p):
    r = requests.get(u, params=p, headers=UA, timeout=30); print("GET", r.url, r.status_code); return r.json()
sb = g("https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard", dates="20261018")
ev = sb["events"][0]; c = ev["competitions"][0]
print("evento", ev["id"], ev["name"], "venue", json.dumps(c.get("venue"))[:300])
print("team", json.dumps(c["competitors"][0]["team"])[:500])
s = g("https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/summary", event=ev["id"])
print("summary keys", list(s.keys()))
for k in ("rosters", "headToHeadGames", "standings", "gameInfo", "lastFiveGames", "boxscore"):
    print("==", k, json.dumps(s.get(k))[:1500])
# un partido ya jugado (alineaciones confirmadas)
sb2 = g("https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard", dates="20261005")
if sb2.get("events"):
    s2 = g("https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/summary", event=sb2["events"][0]["id"])
    print("== rosters jugado", json.dumps(s2.get("rosters"))[:2500])
st = g("https://site.api.espn.com/apis/v2/sports/soccer/esp.1/standings")
print("== standings", json.dumps(st)[:2500])
for slug in ("uefa.champions", "uefa.europa", "uefa.europa.conf", "basketball/nba"):
    pass
u = g("https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard", dates="20261020")
print("== ucl", [e["name"] for e in u.get("events", [])][:5])
