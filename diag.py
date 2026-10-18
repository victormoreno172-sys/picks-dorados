import requests, json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"application/json","Accept-Language":"es-ES,es;q=0.9","Referer":"https://www.sofascore.com/","Origin":"https://www.sofascore.com"}
out={}
for u in ["https://api.sofascore.com/api/v1/sport/esports/events/live","https://www.sofascore.com/api/v1/sport/esports/events/live",
          "https://api.sofascore.app/api/v1/sport/esports/events/live"]:
    try:
        x=requests.get(u,headers=H,timeout=30); out[u]=[x.status_code,x.text[:3000]]
    except Exception as e: out[u]=str(e)
# if events, fetch details for FURIA
try:
    for u in list(out):
        if isinstance(out[u],list) and out[u][0]==200:
            ev=json.loads(requests.get(u,headers=H,timeout=30).text).get("events",[])
            out["ev"]=[{k:e.get(k) for k in ("id","homeTeam","awayTeam","homeScore","awayScore","status","tournament")} for e in ev if "FURIA" in json.dumps(e)][:2]
            if out["ev"]:
                eid=out["ev"][0]["id"]; base=u.split("/sport/")[0]
                for p in [f"/event/{eid}", f"/event/{eid}/esports-games"]:
                    y=requests.get(base+p,headers=H,timeout=30); out[p]=[y.status_code,y.text[:4000]]
            break
except Exception as e: out["err"]=str(e)
print(json.dumps(out,indent=1,ensure_ascii=False))
