import json, os, requests
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
P = "appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2"
out = {}
j = requests.get(f"https://webws.365scores.com/web/search/?{P}", params={"query": "Copa del Rey", "filter": "all"}, headers=UA, timeout=30).json()
out["comps"] = [(c.get("id"), c.get("name"), c.get("sportId"), c.get("countryId")) for c in j.get("competitions") or []][:10]
for cid, n, sp, co in out["comps"][:3]:
    if sp != 1: continue
    g = requests.get(f"https://webws.365scores.com/web/games/fixtures/?{P}", params={"competitions": cid}, headers=UA, timeout=30).json()
    gs = g.get("games") or []
    out[f"fx_{cid}"] = [len(gs), [(x.get("startTime"), x.get("roundName"), x.get("stageName"), (x.get("homeCompetitor") or {}).get("name"), (x.get("awayCompetitor") or {}).get("name")) for x in gs[:12]], list(gs[0].keys()) if gs else []]
k = os.environ.get("THESPORTSDB_KEY") or "3"
for lid in ("4483",):
    try:
        r = requests.get(f"https://www.thesportsdb.com/api/v1/json/{k}/eventsnextleague.php?id={lid}", timeout=30).json()
        out["tsdb_next"] = [(e.get("dateEvent"), e.get("intRound"), e.get("strHomeTeam"), e.get("strAwayTeam")) for e in (r.get("events") or [])][:15]
    except Exception as e:
        out["tsdb_next"] = str(e)
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
