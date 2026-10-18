import json, requests
H = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
def prueba(u, h=H):
    try:
        r = requests.get(u, headers=h, timeout=25)
        t = r.text
        return {"status": r.status_code, "acao": r.headers.get("Access-Control-Allow-Origin"), "len": len(t), "inicio": t[:600]}
    except Exception as e:
        return {"error": str(e)[:200]}
ls = "https://prod-public-api.livescore.com/v1/api/app/live/basketball/1?MD=1"
out = {
  "livescore_directo": prueba(ls),
  "livescore_allorigins": prueba("https://api.allorigins.win/raw?url=" + requests.utils.quote(ls, safe="")),
  "livescore_corsproxy": prueba("https://corsproxy.io/?url=" + requests.utils.quote(ls, safe="")),
  "livescore_fecha": prueba("https://prod-public-api.livescore.com/v1/api/app/date/basketball/20261018/1?MD=1"),
  "sofa_www": prueba("https://www.sofascore.com/api/v1/sport/basketball/events/live"),
  "bo3_allorigins": prueba("https://api.allorigins.win/raw?url=" + requests.utils.quote("https://api.bo3.gg/api/v1/matches?filter[matches.status][in]=current&page[limit]=3&with=teams", safe="")),
  "bo3_corsproxy": prueba("https://corsproxy.io/?url=" + requests.utils.quote("https://api.bo3.gg/api/v1/matches?filter[matches.status][in]=current&page[limit]=3&with=teams", safe="")),
  "espn_tenis": prueba("https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"),
}
print(json.dumps(out, indent=1))
