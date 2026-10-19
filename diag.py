import json, re, requests
import directo
UA = directo.UA
out = {}
for est in ("current", "finished"):
    j = requests.get("https://api.bo3.gg/api/v1/matches", headers=UA, timeout=25, params={
        "filter[matches.status][in]": est, "page[limit]": 60, "sort": "-start_date", "with": "teams"}).json()
    for m in j.get("results") or []:
        n = ((m.get("team1") or {}).get("name", "") + "|" + (m.get("team2") or {}).get("name", "")).lower()
        if "mongol" in n or "alliance" in n:
            g = requests.get("https://api.bo3.gg/api/v1/games", headers=UA, timeout=20,
                             params={"filter[games.match_id][eq]": m["id"]}).json().get("results") or []
            out.setdefault("bo3", []).append({"est": est, "m": {k: m.get(k) for k in ("id", "slug", "status", "team1_score", "team2_score", "start_date", "bo_type")},
                "t": n, "games": [{k: x.get(k) for k in ("number", "status", "map_name", "winner_clan_name", "winner_clan_score", "loser_clan_score")} for x in g]})
links = directo._d5_links()
out["d5links"] = [l for l in links if "mongol" in l[1] or "alliance" in l[1]]
out["d5n"] = len(links)
for i, txt in out["d5links"][:3]:
    d = requests.get(directo.D5_API + i, headers=directo.D5_H, timeout=20).json().get("data") or {}
    out["d5_" + i] = {k: d.get(k) for k in ("teamA", "teamB", "seriesScoreA", "seriesScoreB", "isFinished", "isOver", "matchDate", "scores", "tournament", "bestOf")}
    try:
        lv = requests.get(directo.D5_API + i + "/live", headers=directo.D5_H, timeout=20).json().get("data") or []
        out["d5live_" + i] = lv[:3]
    except Exception as e:
        out["d5live_" + i] = str(e)
out["draft5"] = directo.draft5("Alliance", "The MongolZ")
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
