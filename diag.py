import json, re, rankings
out = {"cs2": sorted(rankings.cs2().items(), key=lambda x: x[1]), "val": list(rankings.valorant().items())[:12]}
t = rankings._get("https://www.dust2.us/ranking"); i = t.find('class="ranking-team"'); out["raw"] = t[i:i+2500]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False)
