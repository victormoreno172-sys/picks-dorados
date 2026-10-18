import json, requests
H = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
B = "https://webws.365scores.com/web"
P = "appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2"
out = {}
def g(u):
    try:
        r = requests.get(u, headers=H, timeout=25); return r.json()
    except Exception as e:
        return {"error": str(e)}
for q in ["acb", "euroleague", "eurocup", "lega basket", "valorant", "counter-strike", "league of legends", "girona"]:
    j = g(f"{B}/search/?{P}&query={requests.utils.quote(q)}&filter=all")
    out["buscar_" + q] = {k: [(x.get("id"), x.get("name"), x.get("sportId"), x.get("countryId")) for x in (j.get(k) or [])][:8] for k in ("competitions", "competitors")}
j = g(f"{B}/games/fixtures/?{P}&competitions=79")
out["fixtures79"] = {"n": len(j.get("games", [])), "uno": (j.get("games") or [{}])[0].get("startTime"), "paging": j.get("paging")}
j = g(f"{B}/games/results/?{P}&competitions=79")
out["results79"] = {"n": len(j.get("games", [])), "uno": (j.get("games") or [{}])[0].get("startTime"), "paging": j.get("paging")}
j = g(f"{B}/sports/?{P}")
out["sports"] = [(s.get("id"), s.get("name")) for s in j.get("sports", [])]
print(json.dumps(out, indent=1, ensure_ascii=False))
