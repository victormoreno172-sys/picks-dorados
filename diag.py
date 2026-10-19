import json, re, requests, time
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = {"ev": []}
try:
    import socketio
    sio = socketio.Client(logger=False, engineio_logger=False)
    @sio.event
    def connect():
        out["ev"].append("connect")
        sio.emit("readyForMatch", json.dumps({"token": "", "listId": 2398989}))
    @sio.on("scoreboard")
    def sb(d):
        out["ev"].append(["scoreboard", json.dumps(d)[:1500] if not isinstance(d, str) else d[:1500]])
    @sio.on("log")
    def lg(d):
        out["ev"].append(["log", str(d)[:300]])
    for tr in (["websocket"], ["polling", "websocket"]):
        try:
            sio.connect("https://scorebot-lb.hltv.org", transports=tr, headers={"User-Agent": UA, "Origin": "https://www.hltv.org"})
            time.sleep(12)
            sio.disconnect()
            break
        except Exception as e:
            out["ev"].append(["err", str(tr), repr(e)[:300]])
except Exception as e:
    out["sio"] = repr(e)
def g(u, h=None):
    try:
        r = requests.get(u, headers={"User-Agent": UA, **(h or {})}, timeout=25); return r.status_code, r.text
    except Exception as e: return 0, str(e)
s, t = g("https://www.vlr.gg/matches/results")
l = re.findall(r'href="(/\d+/[a-z0-9-]+)"', t)
out["vlr_first"] = l[:3]
if l:
    s, t = g("https://www.vlr.gg" + l[0])
    i = t.find("vm-stats-game-header")
    out["vlr_match"] = t[max(0, i-300):i+3500]
    i = t.find("match-header-vs")
    out["vlr_head"] = t[i:i+2500]
s, t = g("https://www.vlr.gg/matches")
i = t.find("ml-status")
out["vlr_list"] = t[max(0, i-2500):i+600]
K = {"x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"}
s, t = g("https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=es-ES", K)
j = json.loads(t)
evs = j["data"]["schedule"]["events"]
done = [e for e in evs if e.get("state") == "completed" and e.get("match")][-1:]
out["lol_ev"] = json.dumps(done)[:1500]
if done:
    s, t = g(f"https://esports-api.lolesports.com/persisted/gw/getEventDetails?hl=es-ES&id={done[0]['match']['id']}", K)
    out["lol_det"] = t[:2500]
    try:
        gid = json.loads(t)["data"]["event"]["match"]["games"][0]["id"]
        s, t = g(f"https://feed.lolesports.com/livestats/v1/window/{gid}")
        out["lol_win"] = [s, t[:2500]]
    except Exception as e:
        out["lol_win"] = repr(e)
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False, default=str)
