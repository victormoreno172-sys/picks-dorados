import json, re, rankings
out = {}
for u in ("https://www.dust2.us/ranking", "https://www.dust2.us/ranking/2026-10-05"):
    t = rankings._get(u)
    i = t.find("ranking-")
    out[u] = [len(t), sorted(set(re.findall(r'class="([^"]*rank[^"]*)"', t)))[:30], t[t.find('<div class="col'):][:200]]
    j = t.find("Spirit"); out[u + "_sp"] = t[max(0, j-1500):j+300]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False)
