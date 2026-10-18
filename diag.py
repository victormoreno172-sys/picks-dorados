import requests, json
UA={"User-Agent":"Mozilla/5.0"}
B="https://api.bo3.gg/api/v1/"
out={}
t=requests.get(B+"tournaments/thunderpick-world-championship-2026",headers=UA,timeout=40).json()
out["stages"]=t.get("stages")
m=requests.get(B+"matches",params={"filter[matches.id][in]":"131674,131673","with":"stage,round"},headers=UA,timeout=40).json()
out["m"]=[{k:v for k,v in x.items() if k in("id","stage","round","stage_id","round_id","position")} for x in m.get("results",[])]
for slug in ["valorant-champions-2026","worlds-2026","pgl-masters-bucharest-2026"]:
    try:
        tt=requests.get(B+"tournaments/"+slug,headers=UA,timeout=40); out[slug]=[tt.status_code, (tt.json().get("stages") if tt.ok else None)]
    except Exception as e: out[slug]=str(e)
print(json.dumps(out,indent=1)[:120000])
