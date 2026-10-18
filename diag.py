import json, requests
H = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36", "Origin": "https://victormoreno172-sys.github.io"}
def prueba(u, h=H):
    try:
        r = requests.get(u, headers=h, timeout=25)
        return {"status": r.status_code, "acao": r.headers.get("Access-Control-Allow-Origin"), "len": len(r.text), "inicio": r.text[:2500]}
    except Exception as e:
        return {"error": str(e)[:200]}
out = {
 "365_current": prueba("https://webws.365scores.com/web/games/current/?appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2&sports=2"),
 "365_allscores": prueba("https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2&sports=2&onlyLiveGames=true"),
 "flashscore": prueba("https://local-global.flashscore.ninja/2/x/feed/f_3_0_2_es_1", dict(H, **{"x-fsign": "SW9D1eZo"})),
 "aiscore": prueba("https://api.aiscore.com/v1/web/api/basketball/matches/live"),
 "euroleague_header": prueba("https://live.euroleague.net/api/Header?gamecode=1&seasoncode=E2026"),
}
print(json.dumps(out, indent=1, ensure_ascii=False))
