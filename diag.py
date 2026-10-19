import json, re, rankings
out = {}
t = rankings._get("https://www.dust2.us/ranking")
out["links"] = list(set(re.findall(r'href="(/ranking[^"]*)"', t)))[:20]
i = t.find("Vitality"); out["ctx"] = t[max(0, i-2500):i+1000]
t2 = rankings._get("https://www.vlr.gg/rankings"); i = t2.find("Team Vitality"); out["vlr"] = re.sub(r"\s+", " ", t2[max(0, i-3000):i+200])
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False)
