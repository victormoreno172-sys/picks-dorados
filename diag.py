import json, re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = {}
t = requests.get("https://www.dust2.us/matches/2398989/big-vs-private", headers={"User-Agent": UA, "Accept": "text/html"}, timeout=25).text
i = t.find("map-container-map-name\">Cache")
out["cache"] = t[i:i+3500]
out["nums"] = re.findall(r'map-container-score-(?:left|right)[^>]*>(.*?)</div>', t, re.S)[:8]
s = requests.get("https://api.bo3.gg/api/v1/games", headers={"User-Agent": UA}, params={"filter[games.match_id][eq]": 131180}, timeout=20)
r = requests.get("https://api.bo3.gg/api/v1/matches", headers={"User-Agent": UA}, params={"filter[matches.status][in]": "current", "page[limit]": 30, "with": "teams"}, timeout=20).json()
for m in r.get("results") or []:
    if "PRIVATE" in json.dumps(m).upper():
        out["bo3m"] = {k: m.get(k) for k in ("id", "team1_score", "team2_score", "maps_score", "team1_last_game_score", "team2_last_game_score")}
        g = requests.get("https://api.bo3.gg/api/v1/games", headers={"User-Agent": UA}, params={"filter[games.match_id][eq]": m["id"]}, timeout=20).json()
        out["bo3g"] = [{k: x.get(k) for k in ("number", "status", "map_name", "winner_clan_score", "loser_clan_score", "rounds_count", "state")} for x in g.get("results") or []]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
