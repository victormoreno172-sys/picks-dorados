import requests, json, re
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"text/html,application/json,*/*"}
out={}
t=requests.get("https://www.dust2.us/",headers=H,timeout=30).text
out["d2_scorebot"]=list(set(re.findall(r'[\w\-./:]*scorebot[\w\-./:?=&]*',t)))[:40]
out["d2_js"]=list(set(re.findall(r'src="([^"]+\.js[^"]*)"',t)))[:30]
for js in out["d2_js"]:
    u=js if js.startswith("http") else "https://www.dust2.us"+js
    try:
        c=requests.get(u,headers=H,timeout=30).text
        for m in re.finditer(r'scorebot',c):
            out.setdefault("jsctx",[]).append(u+" :: "+c[max(0,m.start()-200):m.start()+300])
    except Exception as e: pass
out["jsctx"]=(out.get("jsctx") or [])[:12]
d=requests.get("https://www.dust2.us/matches/2399417/furia-vs-betboom",headers=H,timeout=30); out["d2_match"]=[d.status_code, re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",d.text))[:3000]]
p=requests.get("https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups/live",headers={**H,"X-API-Key":"CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"},timeout=30).json()
out["pin"]=[m for m in p if "FURIA" in json.dumps(m)][:1]
t=requests.get("https://draft5.gg/",headers=H,timeout=30).text
i=t.find("FURIA"); out["draft5"]=re.sub(r"\s+"," ",re.sub(r"<[^>]+>","|",t[max(0,i-3000):i+3000]))
out["draft5_links"]=list(set(re.findall(r'href="(/partida/[^"]+)"',t)))[:20]
print(json.dumps(out,indent=1,ensure_ascii=False))
