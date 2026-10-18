import requests, json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"*/*","x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/"}
B="https://local-global.flashscore.ninja/2/x/feed/"
out={}
t=requests.get(B+"f_36_0_2_en_1",headers=H,timeout=30).text
i=t.find("FURIA"); a=t.rfind("~AA÷",0,i); out["row"]=t[a:t.find("¬AL÷",a)]
for f in ["dc_1_GEhgO2xe","df_sui_1_GEhgO2xe","df_st_1_GEhgO2xe","df_hh_1_GEhgO2xe","d_su_GEhgO2xe_en_1","df_sur_1_GEhgO2xe","dme_1_GEhgO2xe","df_lc_1_GEhgO2xe"]:
    try:
        x=requests.get(B+f,headers=H,timeout=30); out[f]=[x.status_code,x.text[:3000]]
    except Exception as e: out[f]=str(e)
print(json.dumps(out,indent=1,ensure_ascii=False))
