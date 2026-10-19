import json, rankings
out = {}
for n, f in (("cs2", rankings.cs2), ("val", rankings.valorant), ("lol", rankings.lol), ("atp", lambda: rankings.tenis("atp")), ("wta", lambda: rankings.tenis("wta"))):
    d = f(); out[n] = [len(d), sorted(d.items(), key=lambda x: x[1])[:8]]
t = rankings._get("https://www.dust2.us/ranking"); i = t.find("ranked-team"); out["cs2raw"] = t[i:i+1500]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False)
