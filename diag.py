import requests, json
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124","Accept":"application/json"}
out={}
def g(u,**p):
    try:
        x=requests.get(u,params=p,headers=UA,timeout=30)
        try: return [x.status_code,x.json()]
        except Exception: return [x.status_code,x.text[:800]]
    except Exception as e: return [0,str(e)]
m=g("https://api.bo3.gg/api/v1/matches",**{"filter[matches.id][in]":"131674","with":"teams,games"})
mm=(m[1].get("results") or [{}])[0] if isinstance(m[1],dict) else {}
out["match"]={k:v for k,v in mm.items() if k not in("bet_updates","team1","team2")}
out["games"]=g("https://api.bo3.gg/api/v1/games",**{"filter[games.match_id][eq]":"131674"})
out["slug"]=g("https://api.bo3.gg/api/v1/matches/furia-vs-betboom-18-10-2026")
for sp in ["", "&sports=17"]:
    out["365"+sp]=g("https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=29&timezoneName=Europe/Madrid&userCountryId=2&onlyLiveGames=true"+sp)
out["365s"]=g("https://webws.365scores.com/web/search/?appTypeId=5&langId=29&query=furia")
print(json.dumps(out,indent=1,default=str,ensure_ascii=False)[:200000])
