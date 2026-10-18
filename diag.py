import requests, json, re, html
H={"User-Agent":"PicksDorados/1.0 (github.com/victormoreno172-sys/picks-dorados)","Accept-Encoding":"gzip"}
x=requests.get("https://liquipedia.net/counterstrike/api.php",params={"action":"parse","page":"Liquipedia:Matches","format":"json","prop":"text"},headers=H,timeout=30)
t=x.json()["parse"]["text"]["*"]
out=[]
for m in re.finditer(r'FURIA', t):
    pass
i=t.find('title="FURIA"')
blk=t[max(0,i-6000):i+3000]
txt=re.sub(r"<[^>]+>"," ",blk); txt=re.sub(r"\s+"," ",html.unescape(txt))
print(json.dumps({"txt":txt, "raw":blk[:9000]},ensure_ascii=False))
