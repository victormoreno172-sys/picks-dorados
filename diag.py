import json, requests, os
K = os.environ["ODDS_API_KEY"]; U = "https://api.the-odds-api.com/v4"
out = {}
r = requests.get(f"{U}/sports", params={"apiKey": K}, timeout=30)
out["sports"] = [s["key"] for s in r.json() if s["key"].startswith(("basketball", "soccer_uefa"))]
out["restantes"] = r.headers.get("x-requests-remaining")
for clave, mk in (("soccer_uefa_champs_league", "h2h,totals"), ("basketball_euroleague", "h2h,spreads,totals")):
    r = requests.get(f"{U}/sports/{clave}/odds", params={"apiKey": K, "bookmakers": "winamax_fr,winamax_de,pinnacle", "markets": mk, "oddsFormat": "decimal"}, timeout=30)
    out[clave] = r.json(); out["restantes_" + clave] = r.headers.get("x-requests-remaining"); out["coste_" + clave] = r.headers.get("x-requests-last")
json.dump(out, open("resultado.json", "w"), ensure_ascii=False)
