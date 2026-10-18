"""Diagnóstico temporal: qué fuentes de marcadores en directo se pueden leer desde el móvil (CORS)."""
import json
import os

import requests

ORIGEN = "https://victormoreno172-sys.github.io"
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36",
      "Origin": ORIGEN, "Referer": ORIGEN + "/"}
URLS = {
    "espn_tenis_atp": "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard",
    "espn_tenis_wta": "https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard",
    "bo3_current": "https://api.bo3.gg/api/v1/matches?filter[matches.status][in]=current&page[limit]=5&with=teams",
    "sofascore_basket_live": "https://api.sofascore.com/api/v1/sport/basketball/events/live",
    "tsdb_livescore": "https://www.thesportsdb.com/api/v1/json/123/livescore.php?s=Basketball",
    "tsdb_v2_live": "https://www.thesportsdb.com/api/v2/json/livescore/basketball",
    "euroleague_incrowd": "https://feeds.incrowdsports.com/provider/euroleague-feeds/v2/competitions/E/seasons/E2026/games?teamCode=&phaseTypeCode=RS",
    "euroleague_live": "https://api-live.euroleague.net/v2/competitions/E/seasons/E2026/games",
    "espn_basket_fiba": "https://site.api.espn.com/apis/site/v2/sports/basketball/fiba/scoreboard",
    "livescore_cdn": "https://prod-public-api.livescore.com/v1/api/app/live/basketball/1?MD=1",
    "fotmob": "https://www.fotmob.com/api/matches?date=20261018",
    "allorigins_sofa": "https://api.allorigins.win/raw?url=https%3A%2F%2Fapi.sofascore.com%2Fapi%2Fv1%2Fsport%2Fbasketball%2Fevents%2Flive",
}


def main(carpeta="web"):
    out = {}
    for k, u in URLS.items():
        try:
            r = requests.get(u, headers=UA, timeout=20)
            cuerpo = r.text[:300]
            try:
                j = r.json()
                resumen = list(j.keys())[:6] if isinstance(j, dict) else f"lista {len(j)}"
                n = len((j.get("events") or j.get("data") or j.get("Stages") or j.get("results") or [])) if isinstance(j, dict) else len(j)
            except ValueError:
                resumen, n = cuerpo[:120], None
            out[k] = {"status": r.status_code, "acao": r.headers.get("Access-Control-Allow-Origin"), "claves": resumen, "n": n}
        except Exception as e:  # noqa: BLE001
            out[k] = {"error": str(e)[:200]}
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "diag_cors.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("diag cors:", json.dumps(out, default=str)[:2000])
