import json, requests
from urllib.parse import quote
H = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36", "Origin": "https://victormoreno172-sys.github.io"}
def prueba(u, h=H):
    try:
        r = requests.get(u, headers=h, timeout=25)
        return {"status": r.status_code, "acao": r.headers.get("Access-Control-Allow-Origin"), "len": len(r.text), "inicio": r.text[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}
ls = "https://prod-public-api.livescore.com/v1/api/app/live/basketball/1?MD=1"
proxies = {
  "codetabs": "https://api.codetabs.com/v1/proxy?quest=" + quote(ls, safe=""),
  "codetabs_raw": "https://api.codetabs.com/v1/proxy/?quest=" + ls,
  "cors_eu": "https://cors.eu.org/" + ls,
  "thingproxy": "https://thingproxy.freeboard.io/fetch/" + ls,
  "allorigins_get": "https://api.allorigins.win/get?url=" + quote(ls, safe=""),
  "whateverorigin": "https://whateverorigin.org/get?url=" + quote(ls, safe=""),
  "corsfix": "https://proxy.corsfix.com/?" + ls,
  "everyorigin": "https://everyorigin.jwvbremen.nl/api/get?url=" + quote(ls, safe=""),
  "livescore_static": "https://prod-cdn-public-api.livescore.com/v1/api/app/live/basketball/1?MD=1",
  "livescore_mev": "https://prod-cdn-mev-api.livescore.com/v1/api/app/live/basketball/1?MD=1",
  "lsc_noorigin_hdrs": "https://prod-public-api.livescore.com/v1/api/app/live/basketball/1?MD=1",
}
out = {k: prueba(u) for k, u in proxies.items()}
print(json.dumps(out, indent=1))
