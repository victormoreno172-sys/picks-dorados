import json, requests, glob, os
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "application/json"}
def g(u, **p):
    try:
        r = requests.get(u, params=p, headers=UA, timeout=30); print("GET", r.url, r.status_code); return r.json()
    except Exception as e:
        print("ERR", u, e); return {}
# 1) TSDB: campos de un evento de basket cacheado y tabla
fs = sorted(glob.glob("cache/basket/tsdb_4408_2026-2027_*.json"))
print("tsdb ficheros", len(fs))
for f in fs[:1]:
    ev = (json.load(open(f)) or {}).get("events") or []
    if ev: print("evento tsdb", {k: v for k, v in ev[0].items() if v and k.startswith(("str", "id"))})
t = g("https://www.thesportsdb.com/api/v1/json/123/lookuptable.php", l="4408", s="2026-2027")
print("tabla tsdb", json.dumps(t)[:800])
t2 = g("https://www.thesportsdb.com/api/v1/json/123/lookuptable.php", l="4328", s="2025-2026")
print("tabla tsdb futbol", json.dumps(t2)[:300])
# 2) Sofascore
s = g("https://api.sofascore.com/api/v1/sport/basketball/scheduled-events/2026-10-18")
print("sofascore", json.dumps(s)[:600])
s2 = g("https://www.sofascore.com/api/v1/sport/basketball/scheduled-events/2026-10-18")
print("sofascore www", json.dumps(s2)[:300])
# 3) ESPN tenis: campos del jugador
te = g("https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard")
try:
    c = te["events"][0]["groupings"][0]["competitions"][0]
    print("tenis comp keys", list(c.keys())); print("tenis competitor", json.dumps(c["competitors"][0])[:900]); print("venue", c.get("venue"))
except Exception as e: print("tenis err", e)
# 4) bo3.gg equipo
b = g("https://api.bo3.gg/api/v1/matches", **{"page[limit]": 1, "filter[matches.discipline_id][eq]": 3, "with": "teams,tournament"})
try:
    m = b["results"][0]; print("bo3 team1", json.dumps(m.get("team1"))[:600]); print("bo3 tournament", json.dumps(m.get("tournament"))[:400])
except Exception as e: print("bo3 err", e, json.dumps(b)[:300])
# 5) API-Basketball libre? (api-sports necesita clave) / ESPN euroleague?
for slug in ("mens-euroleague", "euroleague", "fiba"):
    g(f"https://site.api.espn.com/apis/site/v2/sports/basketball/{slug}/scoreboard")
