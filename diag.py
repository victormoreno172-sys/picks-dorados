import requests, json
UA={"User-Agent":"Mozilla/5.0"}
B="https://api.bo3.gg/api/"
out={}
def g(u,**p):
    try:
        x=requests.get(B+u,params=p,headers=UA,timeout=40)
        try: return [x.status_code, x.json()]
        except Exception: return [x.status_code, x.text[:300]]
    except Exception as e: return [0,str(e)]
t=g("v1/tournaments/thunderpick-world-championship-2026")
out["tour_keys"]=list(t[1].keys()) if isinstance(t[1],dict) else t
tests=[("v1/stages",{"filter[stages.id][in]":"10936,10937,10938,10997"}),
 ("v1/stages",{"filter[stages.tournament_id][in]":"5111"}),
 ("v1/tournament_rounds",{"filter[tournament_rounds.id][in]":"40832,40834,40912"}),
 ("v1/stage_rounds",{"filter[stage_rounds.id][in]":"40832,40834"}),
 ("v1/matches/131674",{}),
 ("v1/matches/furia-vs-betboom-18-10-2026",{"with":"stage,round,tournament"}),
 ("v1/tournaments/thunderpick-world-championship-2026",{"with":"stages,rounds"}),
 ("v1/tournaments/5111/stages",{}),
 ("v1/tournaments/5111/brackets",{}),
 ("v2/tournaments/thunderpick-world-championship-2026/stages",{}),
 ("v1/matches",{"filter[matches.id][in]":"131674,131673","with":"stage,round"}),
 ("v1/matches",{"filter[matches.id][in]":"131674,131673","with":"tournament_stage,tournament_round"}),
]
for u,p in tests:
    r=g(u,**p); out[u+" "+json.dumps(p)]=[r[0], json.dumps(r[1])[:2500]]
print(json.dumps(out,indent=1))
