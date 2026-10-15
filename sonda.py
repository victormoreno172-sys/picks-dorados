import json, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "application/json"}
for d in range(1, 9):
    try:
        r = requests.get("https://api.bo3.gg/api/v1/matches", headers=UA, timeout=30, params={
            "page[limit]": 20, "sort": "-start_date", "filter[matches.discipline_id][eq]": d,
            "filter[matches.status][in]": "upcoming,current,finished", "with": "teams,tournament"})
        j = r.json()
        ms = j.get("results") or j.get("data") or []
        print("disc", d, r.status_code, len(ms), sorted({((m.get("tournament") or {}).get("name") or "") for m in ms})[:8])
    except Exception as e:
        print("disc", d, e)
for path in ("disciplines", "games"):
    try:
        r = requests.get(f"https://api.bo3.gg/api/v1/{path}", headers=UA, timeout=30)
        print(path, r.status_code, r.text[:800])
    except Exception as e:
        print(path, e)
K = {"x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"}
try:
    r = requests.get("https://esports-api.lolesports.com/persisted/gw/getSchedule", headers=K, params={"hl": "es-ES"}, timeout=30)
    ev = r.json()["data"]["schedule"]["events"]
    print("lolesports", r.status_code, len(ev))
    for e in ev[-60:]:
        m = e.get("match") or {}
        print(" ", e.get("startTime"), e.get("state"), (e.get("league") or {}).get("name"), e.get("blockName"),
              [ (t.get("code"), (t.get("result") or {}).get("gameWins")) for t in m.get("teams", [])], (m.get("strategy") or {}))
except Exception as e:
    print("lolesports", e)
