import requests, json
UA={"User-Agent":"Mozilla/5.0"}
out={}
r=requests.get("https://api.bo3.gg/api/v1/matches",params={"page[limit]":3,"sort":"-start_date","filter[matches.status][in]":"finished","filter[matches.discipline_id][eq]":1,"filter[matches.tier][in]":"s,a","with":"teams,tournament,stage,tournament_stage"},headers=UA,timeout=40)
j=r.json(); out["match"]=(j.get("results") or [None])[0]; out["keys_top"]=list(j.keys())
m=out["match"] or {}
tid=m.get("tournament_id"); out["tid"]=tid
for u in [f"https://api.bo3.gg/api/v1/tournaments/{tid}", f"https://api.bo3.gg/api/v1/tournaments/{(m.get('tournament') or {}).get('slug')}",
          f"https://api.bo3.gg/api/v1/tournament_stages?filter[tournament_stages.tournament_id][eq]={tid}",
          f"https://api.bo3.gg/api/v1/stages?filter[stages.tournament_id][eq]={tid}",
          f"https://api.bo3.gg/api/v1/brackets?filter[brackets.tournament_id][eq]={tid}"]:
    try:
        x=requests.get(u,headers=UA,timeout=30); out[u]=[x.status_code, x.text[:4000]]
    except Exception as e: out[u]=str(e)
print(json.dumps(out,indent=1,default=str)[:60000])
