import json, re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = {}
def g(u, h=None):
    try:
        r = requests.get(u, headers={"User-Agent": UA, **(h or {})}, timeout=25); return r.status_code, r.text
    except Exception as e: return 0, str(e)
# Flashscore esports (sport 36)
FS = {"x-fsign": "SW9D1eZo", "Origin": "https://www.flashscore.es", "Referer": "https://www.flashscore.es/"}
for f in ("f_36_0_2_es_1",):
    s, t = g("https://local-global.flashscore.ninja/2/x/feed/" + f, FS)
    out["fs_status"] = s
    evs = t.split("~AA÷")
    out["fs_n"] = len(evs)
    keep = [e for e in evs if re.search(r"BIG|PRIVATE|ACES|BAKS|Bushido|Sinners|PARIVISION|fnatic", e, re.I)]
    out["fs_ev"] = [e[:1500] for e in keep[:4]]
    ids = [e.split("¬")[0] for e in keep[:2]]
    for i in ids:
        for d in ("df_sui_1_", "df_mh_1_", "df_st_1_", "dc_1_", "df_li_1_", "df_lc_1_"):
            s2, t2 = g("https://local-global.flashscore.ninja/2/x/feed/" + d + i, FS)
            out[d + i] = [s2, t2[:1500]]
# 365scores esports
for sp in range(9, 20):
    s, t = g(f"https://webws.365scores.com/web/games/current/?appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2&sports={sp}")
    try:
        j = json.loads(t); gs = j.get("games") or []
        out[f"365_{sp}"] = [s, len(gs), [(x.get("homeCompetitor", {}).get("name"), x.get("awayCompetitor", {}).get("name"), x.get("statusText")) for x in gs[:5]]]
        hit = [x for x in gs if re.search(r"BIG|PRIVATE|ACES|BAKS", json.dumps(x))]
        if hit:
            out[f"365_{sp}_hit"] = json.dumps(hit[0])[:2500]
            s2, t2 = g(f"https://webws.365scores.com/web/game/?appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2&gameId={hit[0]['id']}")
            out[f"365_{sp}_game"] = t2[:5000]
    except Exception as e:
        out[f"365_{sp}"] = [s, str(e)[:100]]
# dust2.us
s, t = g("https://www.dust2.us/matches", {"Accept": "text/html"})
out["d2"] = [s, list(set(re.findall(r'/matches/\d+/[a-z0-9-]+', t)))[:30]]
for l in out["d2"][1]:
    if "big" in l or "aces" in l:
        s2, t2 = g("https://www.dust2.us" + l, {"Accept": "text/html"})
        out["d2_" + l] = [s2, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", t2))[:3000], list(set(re.findall(r'scorebot[^"\']{0,80}', t2)))[:5]]
        break
# vlr live
s, t = g("https://www.vlr.gg/matches", {"Accept": "text/html"})
out["vlr_live"] = [m.group(0)[:300] for m in re.finditer(r'href="/\d+/[^"]+"[^>]*>(?:(?!</a>).){0,3000}?LIVE', t, re.S)][:3]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
