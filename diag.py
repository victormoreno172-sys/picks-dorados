import json, requests, re
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"}
out = {}
j = requests.get("https://api.bo3.gg/api/v1/matches", headers=UA, timeout=25, params={"filter[matches.status][in]": "finished", "page[limit]": 60, "sort": "-start_date", "with": "teams"}).json()
rs = j.get("results") or []
out["bo3_keys"] = list(rs[0].keys()) if rs else []
out["bo3_sample"] = [{k: m.get(k) for k in m if not isinstance(m.get(k), (dict, list)) or k in ("team1", "team2")} for m in rs if "Wolves" in json.dumps(m) or "Questions" in json.dumps(m)][:3]
out["bo3_disc"] = sorted({str(m.get("discipline_id")) + "|" + str(m.get("game_version") or m.get("discipline") or "") for m in rs})
t = requests.get("https://www.vlr.gg/matches/results", headers={**UA, "Accept": "text/html"}, timeout=25).text
i = t.find("Unsettled"); out["vlr_res"] = t[max(0, i - 3000):i + 1500] if i >= 0 else t[:4000]
t2 = requests.get("https://www.vlr.gg/matches", headers={**UA, "Accept": "text/html"}, timeout=25).text
i = t2.find("Dragon"); out["vlr_up"] = t2[max(0, i - 2500):i + 1500] if i >= 0 else "no dragon"
json.dump(out, open("resultado.json", "w"), ensure_ascii=False, default=str)
