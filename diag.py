import json, directo
out = {}
out["d2"] = directo._d2_lista()[:5]
out["hltv"] = directo.hltv("BIG", "PRIVATE")
out["vlr_lista"] = directo._vlr_lista()[:5]
directo._VLR["lista"] = [{"url": "/754737/loud-vs-team-vitality-valorant-champions-2026-gf", "n1": "LOUD", "n2": "Team Vitality"}]
directo._VLR["t"] = 9e12
out["vlr"] = directo.vlr("Team Vitality", "LOUD")
out["lol"] = directo.lol("x", "y")
out["lol_ev"] = len(directo._LOL["ev"])
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
