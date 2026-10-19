import json, re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = {}
def g(u, h=None):
    try:
        r = requests.get(u, headers={"User-Agent": UA, **(h or {})}, timeout=25); return r.status_code, r.text
    except Exception as e: return 0, str(e)
s, t = g("https://www.dust2.us/matches/2398989/big-vs-private", {"Accept": "text/html"})
i = t.find("map-container-score-live")
out["d2_raw"] = t[max(0, i-2500):i+1500]
s, t = g("https://www.dust2.us/matches", {"Accept": "text/html"})
i = t.find("match-list-live-score")
out["d2_list_raw"] = t[max(0, i-1500):i+1500]
for op in ("ub", "888es", "pafes"):
    s, t = g(f"https://eu-offering-api.kambicdn.com/offering/v2018/{op}/listView/esports/all/all/all/in-play.json?lang=es_ES&market=ES&useCombined=true")
    out["kambi_" + op] = [s, len(t)]
    try:
        j = json.loads(t)
        evs = j.get("events") or []
        out["kambi_" + op].append([(e["event"].get("name"), e.get("liveData", {}).get("score")) for e in evs[:8]])
        hit = [e for e in evs if "liveData" in e]
        if hit:
            out["kambi_live_" + op] = json.dumps(hit[0].get("liveData"))[:2000]
            s2, t2 = g(f"https://eu-offering-api.kambicdn.com/offering/v2018/{op}/event/livedata/{hit[0]['event']['id']}.json?lang=es_ES&market=ES")
            out["kambi_ld_" + op] = [s2, t2[:2500]]
        break
    except Exception as e:
        out["kambi_" + op].append(t[:300])
for u in ("https://1xbet.com/LiveFeed/Get1x2_VZip?sports=40&count=50&lng=en&mode=4&country=1&getEmpty=true",
          "https://1xlite-90823.world/LiveFeed/Get1x2_VZip?sports=40&count=50&lng=en&mode=4&getEmpty=true"):
    s, t = g(u)
    out[u] = [s, t[:300]]
    try:
        j = json.loads(t)
        vs = j.get("Value") or []
        out[u + "_n"] = [(v.get("O1"), v.get("O2"), v.get("SC")) for v in vs if "BIG" in str(v.get("O1")) + str(v.get("O2")) or "Counter" in str(v.get("L"))][:4]
    except Exception:
        pass
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
