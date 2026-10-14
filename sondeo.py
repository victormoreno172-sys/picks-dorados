"""Sondeo temporal: detalles de bo3.gg."""
import json

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept": "application/json"}
B = "https://api.bo3.gg/api/v1/matches"


def js(params):
    r = requests.get(B, params=params, headers=UA, timeout=30)
    print("HTTP", r.status_code, r.url[:200])
    return r.json() if r.ok else {}


d = js({"page[offset]": 0, "page[limit]": 3, "sort": "-start_date", "filter[matches.status][in]": "finished",
        "filter[matches.discipline_id][eq]": 1, "with": "teams,tournament"})
if d.get("results"):
    m = d["results"][0]
    print("claves:", list(m.keys()))
    for k in ("team1", "team2", "tournament", "teams"):
        if k in m:
            print(k, json.dumps(m[k])[:400])
d = js({"page[offset]": 0, "page[limit]": 2, "sort": "-start_date", "filter[matches.status][in]": "finished",
        "filter[matches.discipline_id][eq]": 1, "include": "team1,team2,tournament"})
if d:
    print("include keys:", list(d.keys()), json.dumps(d)[:600])
for lim in (100, 200, 500):
    d = js({"page[offset]": 0, "page[limit]": lim, "sort": "-start_date", "filter[matches.status][in]": "finished",
            "filter[matches.discipline_id][eq]": 2})
    print("limit", lim, "->", len(d.get("results", [])), d.get("total"))
d = js({"page[offset]": 0, "page[limit]": 5, "sort": "-start_date", "filter[matches.status][in]": "finished",
        "filter[matches.discipline_id][eq]": 1, "filter[matches.tier][in]": "s,a"})
print("tier s,a:", [(m.get("tier"), m.get("start_date")) for m in d.get("results", [])], d.get("total"))
d = js({"page[offset]": 0, "page[limit]": 5, "sort": "-start_date", "filter[matches.status][in]": "finished",
        "filter[matches.discipline_id][eq]": 1, "filter[matches.start_date][gte]": "2025-10-14"})
print("fecha gte:", d.get("total"))
for ruta in ("https://api.bo3.gg/api/v1/teams/22184", "https://api.bo3.gg/api/v1/tournaments/6203",
             "https://api.bo3.gg/api/v1/teams?filter[teams.id][in]=22184,22933"):
    r = requests.get(ruta, headers=UA, timeout=30)
    print(ruta, r.status_code, r.text[:500])
