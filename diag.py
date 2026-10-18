import json, fases, ligas
out={}
for slug in ["thunderpick-world-championship-2026","valorant-champions-2026","worlds-2026","pgl-masters-bucharest-2026","valorant-game-changers-championship-2026","demacia-cup-global-invitational-2026"]:
    try:
        E=fases.estructura(slug, slug)
        if not E: out[slug]=None; continue
        jor,gr=ligas._jornadas_fases(E,{})
        out[slug]={"fases":[f["nombre"]+" ["+f["tipo"]+"] "+",".join(f["grupos"]) for f in E["fases"]],
                   "jor":[(j["t"],len(j["p"]),[(p["f"],p["l"],p["v"],p["r"],p["m"],p["st"]) for p in j["p"]][:12]) for j in jor],
                   "grupos":[(g["n"],[(f["eq"],f["g"],f["p"]) for f in g["filas"]]) for g in gr]}
    except Exception as e:
        import traceback; out[slug]=traceback.format_exc()
print(json.dumps(out,indent=1,ensure_ascii=False))
