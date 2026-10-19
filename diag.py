import json, re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = {}
def g(u, h=None):
    try:
        r = requests.get(u, headers={"User-Agent": UA, **(h or {})}, timeout=25); return r.status_code, r.text
    except Exception as e: return 0, str(e)
s, t = g("https://www.dust2.us/matches/2398989/big-vs-private", {"Accept": "text/html"})
out["st"] = s
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", t))
i = txt.find("Dust2.us| |")
out["mapas_txt"] = [txt[m.start()-200:m.start()+400] for m in re.finditer(r"(?i)mapholder|Mirage|Inferno|Nuke|Ancient|Anubis|Train|Overpass|Dust2", txt)][:4]
out["attrs"] = list(set(re.findall(r'data-[a-z-]*(?:scorebot|socket|live|match)[a-z-]*="[^"]{0,200}"', t)))[:20]
out["urls"] = list(set(re.findall(r'(?:https?:)?//[a-z0-9.-]*(?:scorebot|hltv|dust2)[a-z0-9.-]*[^"\'\s<]{0,80}', t)))[:30]
out["classes"] = list(set(re.findall(r'class="([^"]*(?:score|map|live)[^"]*)"', t)))[:40]
for u in ("https://scorebot-lb.hltv.org/socket.io/?EIO=3&transport=polling", "https://scorebot-secure.hltv.org/socket.io/?EIO=3&transport=polling",
          "https://scorebot-lb.hltv.org/socket.io/?EIO=4&transport=polling", "https://www.hltv.org/matches/2398989/big-vs-private"):
    out[u] = list(g(u, {"Origin": "https://www.hltv.org", "Referer": "https://www.hltv.org/"}))
    out[u][1] = out[u][1][:400]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
