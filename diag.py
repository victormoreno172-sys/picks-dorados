import json, tenis, rankings
from datetime import date
out = {}
hist = tenis.historico("ATP", date.today())
ids = {}
for h in hist: ids[h.n1] = h.j1; ids[h.n2] = h.j2
out["hist_sample"] = [(n, i) for n, i in list(ids.items())[:5]] + [("Sinner", ids.get("Jannik Sinner")), ("Khachanov", ids.get("Karen Khachanov"))]
t = rankings._get("https://site.api.espn.com/apis/site/v2/sports/tennis/atp/rankings")
j = json.loads(t)
r = j["rankings"][0]["ranks"][:3]
out["rank_sample"] = [(x["athlete"].get("displayName"), x["athlete"].get("id"), x["athlete"].get("uid"), x["athlete"].get("guid")) for x in r]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False)
