"""Sondeo temporal: fuentes de esports (CS2 y Valorant)."""
import json

import requests

UA = {"User-Agent": "PicksDorados/1.0 (github.com/victormoreno172-sys/picks-dorados)",
      "Accept": "application/json"}


def probar(nombre, url, n=700, **kw):
    try:
        r = requests.get(url, timeout=30, headers=kw.pop("headers", UA), **kw)
        print(f"### {nombre}: HTTP {r.status_code}, {len(r.content)} bytes")
        if r.ok:
            print("   ", r.text[:n].replace("\n", " "))
        return r
    except Exception as e:
        print(f"### {nombre}: ERROR {str(e)[:150]}")


probar("bo3 cs2 matches", "https://api.bo3.gg/api/v1/matches?page[offset]=0&page[limit]=5&sort=-start_date&filter[matches.status][in]=finished&filter[matches.discipline_id][eq]=1")
probar("bo3 cs2 upcoming", "https://api.bo3.gg/api/v1/matches?page[offset]=0&page[limit]=5&sort=start_date&filter[matches.status][in]=upcoming&filter[matches.discipline_id][eq]=1")
probar("bo3 disciplines", "https://api.bo3.gg/api/v1/disciplines", 500)
probar("vlrggapi upcoming", "https://vlrggapi.vercel.app/match?q=upcoming", 500)
probar("vlrggapi results", "https://vlrggapi.vercel.app/match?q=results", 500)
probar("vlr.gg matches html", "https://www.vlr.gg/matches", 200)
probar("hltv matches", "https://www.hltv.org/matches", 200)
probar("liquipedia cs api", "https://liquipedia.net/counterstrike/api.php?action=query&list=categorymembers&cmtitle=Category:S-Tier_Tournaments&format=json&cmlimit=5", 500,
       headers={**UA, "Accept-Encoding": "gzip"})
probar("pandascore sin clave", "https://api.pandascore.co/csgo/matches/upcoming", 200)
probar("tsdb esports cs", "https://www.thesportsdb.com/api/v1/json/123/search_all_leagues.php?s=ESports", 1500)
probar("gamescorekeeper", "https://api.gamescorekeeper.com/v1/fixtures?sport=cs2", 200)
probar("strafe", "https://api.strafe.com/v1.4/matches", 200)
probar("esportsapi abios", "https://atlas.abiosgaming.com/v3/series", 200)
