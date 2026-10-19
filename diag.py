import json, re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = {}
def g(u, h=None):
    try:
        r = requests.get(u, headers={"User-Agent": UA, **(h or {})}, timeout=25); return r.status_code, r.text
    except Exception as e: return 0, str(e)
for u in ("https://www.strafe.com/esports-betting/live/", "https://www.strafe.com/csgo/", "https://www.gosugamers.net/counter-strike/matches",
          "https://www.rivalry.com/esports/cs2-betting", "https://www.esportsbets.com/", "https://www.oddsportal.com/esports/",
          "https://api.sofascore.com/api/v1/sport/esports/events/live", "https://www.sofascore.com/api/v1/sport/esports/events/live",
          "https://www.livescore.com/en/esports/", "https://www.scorebat.com/", "https://www.aiscore.com/esports",
          "https://api.esportsbattle.com", "https://www.bet365.com", "https://cs2-api.org/"):
    s, t = g(u, {"Accept": "text/html,application/json"})
    hits = [t[max(0, m.start()-300):m.start()+700] for m in re.finditer(r"(?i)private", t)][:2]
    out[u] = [s, len(t), hits, list(set(re.findall(r'https://[a-z0-9.-]*api[a-z0-9.-]*\.[a-z]+/[^"\'\s\\]{0,60}', t)))[:12]]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
