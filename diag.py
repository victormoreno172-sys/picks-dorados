import json, requests
out = {}
r = requests.get("https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/live", timeout=30).json()
out["live"] = [x["name"] for x in r] if isinstance(r, list) else r
if isinstance(r, list):
    years = sorted(x["name"] for x in r if x["type"] == "dir")
    if years:
        r2 = requests.get(f"https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/live/{years[-1]}", timeout=30).json()
        names = sorted(x["name"] for x in r2)
        out["files"] = names[-8:]
        g = [n for n in names if "global" in n]
        if g:
            t = requests.get(f"https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/main/live/{years[-1]}/{g[-1]}", timeout=30).text
            out["head"] = t[:1500]
json.dump(out, open("resultado.json", "w"), indent=1, ensure_ascii=False)
