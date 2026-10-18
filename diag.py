import json, requests
H = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
out = {}
j = requests.get("https://prod-public-api.livescore.com/v1/api/app/live/basketball/2?MD=1", headers=H, timeout=25).json()
evs = [e for s in j.get("Stages", []) for e in s.get("Events", []) if e.get("Eps") not in ("HT", "FT")]
out["n_live"] = len(evs)
if evs:
    eid = evs[0]["Eid"]; out["ev"] = {k: v for k, v in evs[0].items() if k not in ("T1", "T2")}
    for nombre, u in {"scoreboard": f"https://prod-public-api.livescore.com/v1/api/app/scoreboard/basketball/{eid}?MD=1",
                      "incidents": f"https://prod-public-api.livescore.com/v1/api/app/incidents/basketball/{eid}?MD=1",
                      "statistics": f"https://prod-public-api.livescore.com/v1/api/app/statistics/basketball/{eid}?MD=1"}.items():
        try:
            r = requests.get(u, headers=H, timeout=25)
            out[nombre] = {"status": r.status_code, "texto": r.text[:1500]}
        except Exception as e:
            out[nombre] = str(e)
print(json.dumps(out, indent=1, ensure_ascii=False))
