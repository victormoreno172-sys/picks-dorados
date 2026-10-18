import json, requests
H = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36", "Origin": "https://victormoreno172-sys.github.io"}
j = requests.get("https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2&sports=2&onlyLiveGames=true", headers=H, timeout=25).json()
g = j.get("games", [])
out = {"n": len(g), "competiciones": [(c.get("id"), c.get("name"), c.get("countryId")) for c in j.get("competitions", [])][:40], "juego": g[:2]}
for s in (1, 3):
    try:
        jj = requests.get(f"https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2&sports={s}&onlyLiveGames=true", headers=H, timeout=25).json()
        out[f"sport{s}"] = {"n": len(jj.get("games", [])), "uno": (jj.get("games") or [None])[0]}
    except Exception as e:
        out[f"sport{s}"] = str(e)
print(json.dumps(out, indent=1, ensure_ascii=False))
