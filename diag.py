import json, requests
H = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
out = {}
j = requests.get("https://prod-public-api.livescore.com/v1/api/app/live/basketball/2?MD=1", headers=H, timeout=25).json()
evs = [e for s in j.get("Stages", []) for e in s.get("Events", [])]
out["ls_live"] = evs[:2]
j2 = requests.get("https://prod-public-api.livescore.com/v1/api/app/date/basketball/20261018/2?MD=1", headers=H, timeout=25).json()
out["ls_ft"] = [e for s in j2.get("Stages", []) for e in s.get("Events", []) if e.get("Eps") == "FT"][:1]
for w in ("teams,games", "teams,match_maps", "teams"):
    try:
        b = requests.get("https://api.bo3.gg/api/v1/matches", headers=H, timeout=25, params={"filter[matches.status][in]": "current,finished", "page[limit]": 2, "sort": "-start_date", "with": w}).json()
        out["bo3_" + w] = b.get("results", [])[:1]
    except Exception as e:
        out["bo3_" + w] = str(e)
try:
    r = (out.get("bo3_teams") or [{}])[0]
    slug = r.get("slug")
    out["bo3_detalle"] = requests.get(f"https://api.bo3.gg/api/v1/matches/{slug}", headers=H, timeout=25, params={"with": "games"}).json()
    out["bo3_games"] = requests.get("https://api.bo3.gg/api/v1/games", headers=H, timeout=25, params={"filter[games.match_id][eq]": r.get("id")}).json()
except Exception as e:
    out["bo3_detalle"] = str(e)
print(json.dumps(out, indent=1, ensure_ascii=False)[:60000])
