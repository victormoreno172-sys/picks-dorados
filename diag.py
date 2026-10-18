import requests, json, re
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"application/json, text/plain, */*","Origin":"https://draft5.gg","Referer":"https://draft5.gg/"}
out={}
for u in ["https://api.draft5.gg/matches/47131","https://api.draft5.gg/matches/47131/maps","https://api.draft5.gg/matches/47131/scoreboard","https://api.draft5.gg/matches/47131/live"]:
    try:
        x=requests.get(u,headers=H,timeout=30); out[u]=[x.status_code,x.text[:6000]]
    except Exception as e: out[u]=str(e)
t=requests.get("https://draft5.gg/partida/47131-BETBOOM-vs-FURIA-Thunderpick-World-Championship-2026",headers={**H,"Accept":"text/html"},timeout=30).text
out["page_txt"]=re.sub(r"\s+"," ",re.sub(r"<[^>]+>","|",t))[:200]
out["page_api"]=list(set(re.findall(r'https://[a-z0-9.\-]*draft5[a-z0-9.\-]*/[^"\'\s\\]*',t)))[:40]
i=t.find("Dust2"); out["page_dust2"]=re.sub(r"\s+"," ",re.sub(r"<[^>]+>","|",t[max(0,i-2000):i+2000])) if i>=0 else None
# next data chunks with round/score
for k in ["roundsTeam","scoreA","score_a","rounds","currentRound","ct_score","t_score","liveScore"]:
    j=t.find(k); out["k_"+k]=t[max(0,j-300):j+500] if j>=0 else None
print(json.dumps(out,indent=1,ensure_ascii=False))
