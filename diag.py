import requests, json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"application/json, text/plain, */*","Origin":"https://draft5.gg","Referer":"https://draft5.gg/"}
d=requests.get("https://api.draft5.gg/matches/47131",headers=H,timeout=30).json()["data"]
out={"keys":list(d.keys())}
for k,v in d.items():
    if k not in("tournament","playByPlayAuthor","mainStream"): out[k]=v
l=requests.get("https://api.draft5.gg/matches/47131/live",headers=H,timeout=30).json()["data"]
out["live_first"]=l[:2]; out["live_n"]=len(l)
for u in ["https://api.draft5.gg/matches?page=1&amount=20&finished=0","https://api.draft5.gg/matches?finished=0&featured=1","https://api.draft5.gg/matches/upcoming","https://api.draft5.gg/matches?isFinished=0&page=1&amount=20"]:
    try:
        x=requests.get(u,headers=H,timeout=30); out[u]=[x.status_code,x.text[:600]]
    except Exception as e: out[u]=str(e)
print(json.dumps(out,indent=1,ensure_ascii=False)[:30000])
