import json, re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = {}
def g(u, h=None):
    try:
        r = requests.get(u, headers={"User-Agent": UA, **(h or {})}, timeout=25); return r.status_code, r.text
    except Exception as e: return 0, str(e)
SR = {"Origin": "https://s5.sir.sportradar.com", "Referer": "https://s5.sir.sportradar.com/"}
for u in ("https://lsc.fn.sportradar.com/common/en/Etc:UTC/gismo/sport_matches/109/2026-10-19",
          "https://lsc.fn.sportradar.com/common/en/Etc:UTC/gismo/event_fullfeed/0/1/109",
          "https://lsc.fn.sportradar.com/sportradar/en/Europe:Berlin/gismo/config_tree_mini/41/0/109",
          "https://lsc.fn.sportradar.com/common/en/Etc:UTC/gismo/livescore_matches/109"):
    s, t = g(u, SR); out[u] = [s, len(t), t[:400]]
    i = t.find("PRIVATE"); 
    if i < 0: i = t.find("Private")
    if i >= 0: out[u + "_hit"] = t[max(0, i-1500):i+1500]
P = {"X-API-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R", "Referer": "https://www.pinnacle.com/"}
s, t = g("https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups/live", P)
try:
    j = json.loads(t); hit = [m for m in j if "BIG" in json.dumps(m)]
    out["pin"] = [s, len(j), json.dumps(hit[:1])[:2500]]
except Exception as e:
    out["pin"] = [s, t[:300]]
# GosuGamers / escorenews / egamersworld quick reach
for u in ("https://escorenews.com/en/csgo/live", "https://egamersworld.com/counterstrike/matches", "https://www.gosugamers.net/counter-strike/matches",
          "https://www.strafe.com/esports-betting/live/", "https://bo3.gg/matches/current", "https://api.pandascore.co/csgo/matches/running"):
    s, t = g(u, {"Accept": "text/html"}); i = t.find("PRIVATE")
    out[u] = [s, len(t), t[max(0, i-600):i+900] if i >= 0 else ""]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
