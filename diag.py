import json, re, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "application/json"}
out = {}
def g(url, **k):
    try:
        r = requests.get(url, headers=k.pop("h", UA), timeout=25, **k)
        return r.status_code, r.text
    except Exception as e:
        return 0, str(e)
st, t = g("https://api.bo3.gg/api/v1/matches", params={"filter[matches.status][in]": "current", "page[limit]": 20, "with": "teams"})
ms = json.loads(t).get("results") or []
out["current"] = []
for m in ms[:6]:
    out["current"].append({"id": m["id"], "slug": m.get("slug"), "disc": m.get("discipline_id"), "keys": sorted(m.keys()),
                           "live": {k: m.get(k) for k in m if "live" in k or "score" in k or "round" in k}})
if ms:
    m = ms[0]
    st, t = g("https://api.bo3.gg/api/v1/games", params={"filter[games.match_id][eq]": m["id"]})
    out["games_full"] = json.loads(t).get("results")
    for gm in out["games_full"] or []:
        if gm.get("status") == "current":
            for path in (f"games/{gm['id']}", f"games/{gm['id']}?with=rounds", f"games/{gm['id']}/rounds", f"rounds?filter[rounds.game_id][eq]={gm['id']}",
                         f"games/{gm['id']}/live", f"matches/{m['slug']}/live", f"games/{gm['id']}/game_rounds"):
                s2, t2 = g("https://api.bo3.gg/api/v1/" + path)
                out["try_" + path] = [s2, t2[:1500]]
    s2, t2 = g(f"https://bo3.gg/matches/{m['slug']}", h={"User-Agent": UA["User-Agent"], "Accept": "text/html"})
    out["html_status"] = s2
    out["html_ws"] = list(set(re.findall(r'wss?://[^"\'\s]+', t2)))[:10]
    out["html_api"] = list(set(re.findall(r'https://[a-z0-9.-]*bo3\.gg/[^"\'\s]{0,60}', t2)))[:30]
for u in ("https://www.vlr.gg/matches", "https://esports-api.lolesports.com/persisted/gw/getLive?hl=es-ES", "https://feed.lolesports.com/livestats/v1/window/1"):
    h = {"User-Agent": UA["User-Agent"]}
    if "lolesports" in u: h["x-api-key"] = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    s2, t2 = g(u, h=h)
    out[u] = [s2, t2[:800]]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
