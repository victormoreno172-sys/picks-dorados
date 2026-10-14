"""Sondeo temporal: cobertura por jornadas en TheSportsDB."""
import time
from collections import Counter

import requests

B = "https://www.thesportsdb.com/api/v1/json/123/"

for lid in ("4480", "4481", "5071"):
    for r in list(range(1, 13)) + [100, 125, 150, 160, 170, 180, 200, 500]:
        try:
            ev = requests.get(B + f"eventsround.php?id={lid}&r={r}&s=2026-2027", timeout=30).json().get("events") or []
        except Exception as e:
            print(lid, r, "ERR", str(e)[:80]); ev = []
        if ev:
            dias = Counter((e.get("strTimestamp") or e.get("dateEvent") or "")[:10] for e in ev)
            con_res = sum(e.get("intHomeScore") not in (None, "") for e in ev)
            print(f"{lid} r={r}: {len(ev)} partidos, {con_res} con resultado, dias {sorted(dias.items())}")
            if "2026-10-14" in dias or "2026-10-15" in dias:
                print("   ", [(e["strHomeTeam"], e["strAwayTeam"]) for e in ev][:20])
        time.sleep(2.1)
