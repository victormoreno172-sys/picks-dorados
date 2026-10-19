import json, rankings
d = rankings.todos()
json.dump({k: sorted(v.items(), key=lambda x: int(x[1].split()[0][1:]))[:6] for k, v in d.items()}, open("resultado.json", "w"), indent=1, ensure_ascii=False)
