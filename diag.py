import requests, json, re
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"application/json, text/html","Accept-Language":"es-ES,es;q=0.9"}
out={}
for u in ["https://www.hltv.org/matches","https://thunderpick.io/api/matches/2843826","https://thunderpick.io/api/v1/matches/2843826",
          "https://thunderpick.io/api/matches/esports?gameIds=2","https://api.draft5.gg/matches?status=live","https://draft5.gg/api/matches/live",
          "https://liquipedia.net/counterstrike/api.php?action=parse&page=Liquipedia:Matches&format=json&prop=text",
          "https://www.gosugamers.net/counterstrike/matches","https://escorenews.com/en/csgo/matches"]:
    try:
        x=requests.get(u,headers=H,timeout=30); t=x.text
        i=t.find("FURIA"); out[u]=[x.status_code,len(t),t[max(0,i-300):i+700] if i>=0 else t[:400]]
    except Exception as e: out[u]=str(e)
print(json.dumps(out,indent=1,ensure_ascii=False))
