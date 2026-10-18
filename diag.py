import requests, json
UA={"User-Agent":"Mozilla/5.0"}
out={}
B="https://api.bo3.gg/api/v1/"
def g(u,**p):
    try:
        x=requests.get(B+u,params=p,headers=UA,timeout=40); return x.status_code, x.json() if x.headers.get("content-type","").startswith("application/json") else x.text[:500]
    except Exception as e: return 0,str(e)
st,j=g("matches",**{"page[limit]":100,"sort":"-start_date","filter[matches.status][in]":"finished,current,upcoming","filter[matches.discipline_id][eq]":1,"filter[matches.tier][in]":"s,a","with":"teams,tournament"})
ms=[m for m in (j.get("results") or []) if "Thunderpick" in ((m.get("tournament") or {}).get("name") or "")]
out["n"]=len(ms)
out["matches"]=[{k:m.get(k) for k in ("id","start_date","status","stage_id","round_id","position","team1_score","team2_score","prev_match1_id","prev_match2_id","bo_type")}|{"t1":(m.get("team1") or {}).get("name"),"t2":(m.get("team2") or {}).get("name"),"tour":(m.get("tournament") or {})} for m in ms]
tid=ms[0]["tournament_id"] if ms else None
out["tid"]=tid
out["stages"]=g("stages",**{"filter[stages.tournament_id][eq]":tid,"page[limit]":50})
rids=sorted({m["round_id"] for m in ms if m.get("round_id")})
for u,p in [("rounds",{"filter[rounds.id][in]":",".join(map(str,rids))}),("rounds",{"filter[rounds.tournament_id][eq]":tid}),
            ("tournaments/%s"%(ms[0]["tournament"]["slug"] if ms and ms[0].get("tournament") else "x"),{}),
            ("matches",{"filter[matches.tournament_id][eq]":tid,"page[limit]":100,"with":"teams,stage,round"})]:
    out[u+json.dumps(p)]=g(u,**p)
print(json.dumps(out,indent=1,default=str)[:150000])
