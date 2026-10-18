import requests, json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"*/*","Accept-Language":"es-ES,es;q=0.9"}
out={}
def g(u,h=None,**p):
    try:
        x=requests.get(u,headers={**H,**(h or {})},params=p,timeout=30); t=x.text
        i=t.find("FURIA"); return [x.status_code,len(t),t[max(0,i-1500):i+2500] if i>=0 else t[:600]]
    except Exception as e: return str(e)
FS={"x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/","Origin":"https://www.flashscore.com"}
for u in ["https://d.flashscore.com/x/feed/f_36_0_2_en_1","https://local-global.flashscore.ninja/2/x/feed/f_36_0_2_en_1","https://www.flashscore.com/x/feed/f_36_0_2_en_1",
          "https://d.flashscore.com/x/feed/r_36_1","https://d.livesport.cz/x/feed/f_36_0_2_en_1"]:
    out[u]=g(u,FS)
out["strafe"]=g("https://flask-api.strafe.com/v1.7/matches/live")
out["hltv_sb"]=g("https://scorebot-lb.hltv.org/socket.io/?EIO=3&transport=polling")
out["livescore_esp"]=g("https://prod-public-api.livescore.com/v1/api/app/live/esports/2?MD=1")
print(json.dumps(out,indent=1,ensure_ascii=False))
