import json, re, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
out = {}
for u in ("https://site.api.espn.com/apis/site/v2/sports/tennis/atp/rankings", "https://sports.core.api.espn.com/v2/sports/tennis/leagues/atp/rankings",
          "https://www.dust2.us/ranking", "https://www.dust2.us/ranking/teams", "https://www.vlr.gg/rankings", "https://lolesports.com/en-US/gpr"):
    try:
        r = requests.get(u, headers={**UA, "Accept": "text/html,application/json"}, timeout=25)
        t = r.text
        i = max(t.find("Sinner"), t.find("Vitality"), t.find("rank"))
        out[u] = [r.status_code, len(t), t[:300], t[max(0, i - 300):i + 900]]
    except Exception as e:
        out[u] = str(e)
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False)
