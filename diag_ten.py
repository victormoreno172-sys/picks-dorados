import json, subprocess
t = subprocess.run(["python", "-u", "calibracion/backtest_tenis.py"], capture_output=True, text=True)
s = t.stdout
i = s.find("{\n")
json.dump({"log": (s[:i] if i >= 0 else s)[-3000:] + t.stderr[-3000:], "res": json.loads(s[i:]) if i >= 0 else None},
          open("resultado.json", "w"), ensure_ascii=False, indent=1)
