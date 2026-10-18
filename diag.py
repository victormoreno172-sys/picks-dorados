import requests, json, re
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"text/html,application/json,*/*","Accept-Language":"es-ES,es;q=0.9"}
out={}
def g(u,h=None,n=2500):
    try:
        x=requests.get(u,headers={**H,**(h or {})},timeout=30); t=x.text
        i=t.find("FURIA"); 
        if i<0: i=t.find("Furia")
        return [x.status_code,len(t),t[max(0,i-800):i+n] if i>=0 else t[:500]]
    except Exception as e: return str(e)
urls=["https://draft5.gg/","https://api.draft5.gg/matches","https://api.draft5.gg/matches/live","https://api.draft5.gg/v2/matches?live=true",
"https://cyberscore.live/en/cs2/","https://api.cyberscore.live/api/v1/matches/live","https://www.egamersworld.com/counterstrike/matches",
"https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups/live","https://www.dust2.com.br/","https://www.dust2.us/",
"https://www.vlr.gg/matches","https://www.gosugamers.net/counterstrike/matches/live","https://escharts.com/","https://www.esportsbets.com/",
"https://www.strafe.com/counter-strike/","https://bo3.gg/matches/current"]
for u in urls: out[u]=g(u)
print(json.dumps(out,indent=1,ensure_ascii=False))
