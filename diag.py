import json, os, requests
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
P = "appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2"
out = {}
r = requests.get(f"https://webws.365scores.com/web/search/?{P}", params={"query": "Copa del Rey", "filter": "all"}, headers=UA, timeout=30)
out["raw"] = r.text[:1500]
# vía equipo: Sevilla
j = requests.get(f"https://webws.365scores.com/web/search/?{P}", params={"query": "Sevilla", "filter": "all"}, headers=UA, timeout=30).json()
cs = [c for c in j.get("competitors") or [] if c.get("sportId") == 1][:2]
out["sev"] = [(c["id"], c["name"]) for c in cs]
if cs:
    g = requests.get(f"https://webws.365scores.com/web/games/fixtures/?{P}", params={"competitors": cs[0]["id"]}, headers=UA, timeout=30).json()
    out["fx"] = [(x.get("startTime"), x.get("competitionDisplayName"), x.get("competitionId"), x.get("roundName"), (x.get("homeCompetitor") or {}).get("name"), (x.get("awayCompetitor") or {}).get("name")) for x in g.get("games") or []][:10]
    cids = {x.get("competitionId") for x in g.get("games") or [] if "Copa" in (x.get("competitionDisplayName") or "")}
    for cid in cids:
        g2 = requests.get(f"https://webws.365scores.com/web/games/fixtures/?{P}", params={"competitions": cid}, headers=UA, timeout=30).json()
        gs = g2.get("games") or []
        out[f"copa_{cid}"] = [len(gs), [(x.get("startTime"), x.get("roundName"), (x.get("homeCompetitor") or {}).get("name"), (x.get("awayCompetitor") or {}).get("name")) for x in gs[:60]]]
k = os.environ.get("THESPORTSDB_KEY") or "3"
for u in (f"https://www.thesportsdb.com/api/v1/json/{k}/eventsnextleague.php?id=4483", f"https://www.thesportsdb.com/api/v2/json/schedule/next/league/4483"):
    try:
        r = requests.get(u, headers={"X-API-KEY": k}, timeout=30); out[u[-40:]] = [r.status_code, r.text[:1200]]
    except Exception as e: out[u[-40:]] = str(e)
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
