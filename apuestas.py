"""
Bot de apuestas: cada noche (hacia las 23:35 de Madrid) manda por Telegram las apuestas del día
siguiente con el importe de cada una para la banca real. Las apuestas se apuntan en
historial/banca.json y se corrigen solas con los resultados (el saldo supone que se hacen todas
a la cuota indicada).

Cada día, de todo un poco (lo pidió el usuario: volumen y movimiento):
  - SENCILLAS: el mejor pick de cada partido con probabilidad >= 70 % y cuota >= 1.20, primero
    las de cuota real de Winamax y las mejor pagadas. Hasta 6. Las que tienen valor (ganan a la
    larga) llevan más importe; las demás, el mínimo.
  - COMBINADA DOBLE y COMBINADA TRIPLE con los picks más seguros (78 %+) de partidos distintos.
  - Importe: cada apuesta es el 5 % del dinero que queda tras hacer las anteriores, en el orden
    del mensaje (lo decidió el usuario). Como mucho 8 apuestas al día.
  - Fútbol, basket y tenis (los que se pueden corregir solos con el resultado). Basket sin cuota en la
    API: hasta 2 sencillas con la cuota mínima que hay que encontrar en Winamax.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from math import prod
from zoneinfo import ZoneInfo

import config
import historial

RUTA = os.path.join(os.path.dirname(historial.RUTA), "banca.json")
TZ = ZoneInfo(config.ZONA_HORARIA)
PROB_MIN, CUOTA_MIN = 0.70, 1.20
PROB_COMBI, CUOTA_PIERNA = 0.78, 1.12
MAX_SENCILLAS = 6
PORCENTAJE = config.PORCENTAJE_APUESTA  # cada apuesta, este % de la banca del momento
PEOR_VALOR = -0.08   # no se apuesta nada que la casa pague muy por debajo de lo que vale


def cargar() -> dict:
    try:
        with open(RUTA, encoding="utf-8") as f:
            b = json.load(f)
    except (OSError, ValueError):
        b = {"inicial": config.BANCA_INICIAL, "apuestas": [], "ultimo_envio": None, "chat": None}
    if not b["apuestas"]:  # todavía sin apuestas: manda la banca que esté configurada
        b["inicial"] = config.BANCA_INICIAL
    return b


def guardar(b: dict):
    os.makedirs(os.path.dirname(RUTA), exist_ok=True)
    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=0)


def _ganancia(a: dict) -> float:
    if a.get("ok") is True:
        return a["importe"] * (a["cuota_final"] - 1)
    if a.get("ok") is False:
        return -a["importe"]
    return 0.0


def saldo(b: dict) -> float:
    # "previa": apuesta hecha antes de empezar la banca; su importe no salió de ella
    extra = sum(a["importe"] for a in b["apuestas"] if a.get("previa") and "ok" in a)
    return round(b["inicial"] + sum(_ganancia(a) for a in b["apuestas"]) + extra, 2)


def corregir(b: dict):
    hoy = datetime.now(TZ).date()
    for a in b["apuestas"]:
        if "ok" in a:
            continue
        for pi in a["piernas"]:
            if "ok" in pi:
                continue
            f = date.fromisoformat(pi["fecha"])
            for d in (f, f - timedelta(days=1), f + timedelta(days=1)):
                res = historial.RESULTADOS.get((d.isoformat(), pi["local"], pi["visitante"]))
                if res:
                    ok = historial.acierta(pi["mercado"], *res, pi["local"], pi["visitante"])
                    if ok is not None:
                        pi["ok"], pi["res"] = ok, list(res)
                    break
            else:
                if (hoy - f).days > 10:  # aplazado: esa pierna se anula (cuota 1)
                    pi["ok"] = None
        if any(pi.get("ok") is False for pi in a["piernas"]):
            a["ok"], a["cuota_final"] = False, a["cuota"]
        elif all("ok" in pi for pi in a["piernas"]):
            vivas = [pi for pi in a["piernas"] if pi["ok"] is True]
            a["cuota_final"] = round(prod(pi["cuota"] for pi in vivas), 2) if vivas else 1.0
            a["ok"] = True if vivas else None


def _deporte(a) -> str:
    return a.partido.deporte or ("b" if config.es_baloncesto(a.partido.liga) else "f")


def _pierna(a, k) -> dict:
    p = a.partido
    return {"fecha": p.fecha.isoformat(), "hora": p.hora, "liga": p.liga, "dep": _deporte(a), "local": p.local,
            "visitante": p.visitante, "mercado": k.mercado, "prob": round(float(k.prob), 3),
            "cuota": float(k.cuota or 0), "estimada": bool(k.estimada)}


def elegir(lista, banca: float, ahora: datetime, cal: dict | None = None) -> list[dict]:
    # Calibración automática: las probabilidades se corrigen con lo que de verdad se ha acertado
    # en cada deporte y tipo de mercado (calibracion_auto.py) antes de elegir.
    if cal:
        import calibracion_auto
        for a in lista:
            for k in a.picks:
                if not hasattr(k, "prob_modelo"):
                    k.prob_modelo = k.prob
                    k.prob = calibracion_auto.ajustar(k.prob, _deporte(a), k.mercado, cal)
    partidos = []
    for a in lista:
        p = a.partido
        if _deporte(a) not in ("f", "b", "te"):  # tenis: modelo calibrado (calibracion/backtest_tenis.py)
            continue
        if p.hora and p.fecha == ahora.date() and p.hora <= ahora.strftime("%H:%M"):
            continue  # ya ha empezado
        buenos = [k for k in a.picks if k.cuota and k.prob >= PROB_MIN and k.cuota >= CUOTA_PIERNA
                  and PEOR_VALOR <= k.prob * k.cuota - 1 <= 0.25]
        if buenos:
            partidos.append((a, buenos))
    redondo = lambda x: max(0.1, round(x, 1))
    apuestas, usados = [], set()

    # Sencillas: el mejor de cada partido (cuota real antes que ≈, y el mejor pagado)
    cand = []
    for a, buenos in partidos:
        ks = [k for k in buenos if k.cuota >= CUOTA_MIN]
        if ks:
            k = max(ks, key=lambda k: (not k.estimada, k.prob * k.cuota))
            cand.append((a, k))
    cand.sort(key=lambda x: (not x[1].estimada, x[1].prob * x[1].cuota), reverse=True)
    for a, k in cand[:MAX_SENCILLAS]:
        apuestas.append({"tipo": "Sencilla", "piernas": [_pierna(a, k)], "cuota": round(k.cuota, 2),
                         "prob": round(k.prob, 3), "importe": redondo(banca * PORCENTAJE)})
        usados.add(id(a))

    # Combinadas con los picks más seguros de partidos distintos (mejor si no están en las sencillas)
    seguros = []
    for a, buenos in partidos:
        ks = [k for k in buenos if k.prob >= PROB_COMBI]
        if ks:
            k = max(ks, key=lambda k: (k.prob * k.cuota, k.prob))
            seguros.append((id(a) in usados, -(k.prob * k.cuota), a, k))
    seguros.sort(key=lambda x: (x[0], x[1]))
    for n, nombre in ((2, "Combinada doble"), (3, "Combinada triple")):
        if len(seguros) >= n:
            piernas = seguros[:n] if n == 2 else (seguros[2:5] if len(seguros) >= 5 else seguros[:3])
            cuota = round(prod(k.cuota for *_, k in piernas), 2)
            apuestas.append({"tipo": nombre, "piernas": [_pierna(a, k) for *_, a, k in piernas],
                             "cuota": cuota, "prob": round(prod(k.prob for *_, k in piernas), 3),
                             "importe": redondo(banca * PORCENTAJE)})

    # Basket y tenis sin cuota en la API (ACB, Lega, torneos pequeños de tenis...): sencillas con la cuota mínima que
    # hay que encontrar en Winamax (la de la app + 3 %). El saldo se calcula con esa cuota mínima.
    sin_cuota = []
    for a in lista:
        p = a.partido
        if _deporte(a) not in ("b", "te") or id(a) in usados or any(k.cuota for k in a.picks):
            continue
        if p.hora and p.fecha == ahora.date() and p.hora <= ahora.strftime("%H:%M"):
            continue
        ks = [k for k in a.picks if PROB_MIN <= k.prob and round(1.03 / k.prob, 2) >= CUOTA_MIN]
        if ks:
            k = max(ks, key=lambda k: k.prob)
            pi = _pierna(a, k)
            pi["cuota"], pi["minima"] = round(1.03 / k.prob + 0.005, 2), True
            sin_cuota.append({"tipo": "Sencilla", "piernas": [pi], "cuota": pi["cuota"],
                              "prob": round(k.prob, 3), "importe": redondo(banca * PORCENTAJE)})
    sin_cuota.sort(key=lambda ap: -ap["prob"])
    # Si hay pocas con cuota real (días flojos de fútbol), más hueco para las de "pide ≥" (tenis y basket)
    hueco = max(2, min(5, MAX_SENCILLAS + 2 - len([x for x in apuestas if x["tipo"] == "Sencilla"])))
    apuestas = [x for x in apuestas if x["tipo"] == "Sencilla"] + sin_cuota[:hueco] + \
               [x for x in apuestas if x["tipo"] != "Sencilla"]

    # Como mucho 10 apuestas (6 sencillas de fútbol/basket con cuota, 2 de basket sin cuota y las
    # 2 combinadas). Con importes en cadena al 5 %, 10 apuestas son ~40 % de la banca.
    elegidas = apuestas[:10]
    for ap in elegidas:
        ap["fecha"] = ap["piernas"][0]["fecha"]
    sencillas = sorted([ap for ap in elegidas if ap["tipo"] == "Sencilla"], key=lambda ap: ap["piernas"][0]["hora"] or "99")
    elegidas = sencillas + [ap for ap in elegidas if ap["tipo"] != "Sencilla"]
    importes_en_cadena(elegidas, banca)
    return elegidas


PCT_MAX = 0.10  # ninguna apuesta pasa del 10 % de lo que queda


def porcentaje(ap: dict) -> float:
    """% de lo que queda que se mete en esta apuesta: el 5 % de base y, si tiene ventaja
    (probabilidad × cuota > 1), un extra de Kelly a la cuarta parte, hasta el 10 %.
    Con cuotas estimadas (≈ o "pide ≥") la ventaja cuenta a la mitad, porque no es segura."""
    c, p = float(ap.get("cuota") or 0), float(ap.get("prob") or 0)
    if c <= 1.0 or p <= 0:
        return PORCENTAJE
    ventaja = p * c - 1
    if any(pi.get("estimada") or pi.get("minima") for pi in ap.get("piernas", [])):
        ventaja /= 2
    kelly = max(0.0, ventaja / (c - 1))
    return round(min(PCT_MAX, PORCENTAJE + kelly / 4), 4)


def importes_en_cadena(apuestas: list[dict], disponible: float):
    """Cada apuesta es su % del dinero que queda después de hacer las anteriores (en este orden)."""
    for ap in apuestas:
        ap["pct"] = porcentaje(ap)
        ap["importe"] = max(0.1, round(disponible * ap["pct"] + 1e-9, 2))
        disponible -= ap["importe"]


def _linea_pierna(pi: dict) -> str:
    cuota = (f"pide ≥ {pi['cuota']:.2f}" if pi.get("minima")
             else f"{'≈' if pi['estimada'] else ''}{pi['cuota']:.2f}")
    return (f"{pi['hora'] or '?'} · {pi['local']} – {pi['visitante']}\n"
            f"   👉 {pi['mercado']} ({pi['prob']:.0%}) · {cuota}")


def _ayer(b: dict, dia: date) -> str:
    ayer = (dia - timedelta(days=1)).isoformat()
    hechas = [a for a in b["apuestas"] if a["fecha"] == ayer and a.get("ok") in (True, False)]
    if not hechas:
        return ""
    neto = sum(_ganancia(a) for a in hechas)
    lineas = [f"{'✅' if a['ok'] else '❌'} {a['tipo']} {a['cuota']:.2f}: "
              + " + ".join(f"{pi['local']}: {pi['mercado']}" for pi in a["piernas"]) + f" ({_ganancia(a):+.2f} €)"
              for a in hechas]
    return (f"📋 <b>Ayer</b>: {sum(a['ok'] for a in hechas)}/{len(hechas)} acertadas, "
            f"<b>{neto:+.2f} €</b>\n" + "\n".join(lineas) + "\n\n")


def mensaje(elegidas: list[dict], b: dict, dia: date) -> str:
    s = saldo(b)
    cerradas = [a for a in b["apuestas"] if a.get("ok") in (True, False)]
    t = [_ayer(b, dia) + f"🟡 <b>Apuestas del {dia:%d/%m}</b>\n"]
    if elegidas:
        for n, ap in enumerate(elegidas, 1):
            t.append(f"<b>{n}. {ap['tipo']}</b> · cuota {ap['cuota']:.2f} · <b>{ap['importe']:.2f} €</b>")
            t += [_linea_pierna(pi) for pi in sorted(ap["piernas"], key=lambda pi: pi["hora"] or "99")]
            t.append("")
        t.append(f"Total del día: <b>{sum(ap['importe'] for ap in elegidas):.2f} €</b>")
        if any(pi["estimada"] for ap in elegidas for pi in ap["piernas"]):
            t.append("≈ = cuota estimada: si en Winamax pagan menos, mira la siguiente o sáltala.")
        if any(pi.get("minima") for ap in elegidas for pi in ap["piernas"]):
            t.append("pide ≥ X = sin cuota en la API: apuéstala solo si Winamax paga X o más.")
    else:
        t.append("Hoy no hay partidos de fútbol o basket que cumplan lo mínimo (70 %+).")
    t.append(f"\n💰 Banca: <b>{s:.2f} €</b> (empezó con {b['inicial']:.0f} €, {s / b['inicial'] - 1:+.1%})"
             + (f" · {sum(a['ok'] for a in cerradas)}/{len(cerradas)} acertadas" if cerradas else ""))
    t.append("<i>Juega con responsabilidad. +18.</i>")
    return "\n".join(t)


def _chat(b: dict) -> str | None:
    if config.TELEGRAM_CANAL:
        return config.TELEGRAM_CANAL
    if b.get("chat"):
        return b["chat"]
    # Sin canal configurado: el chat de la última persona que escribió al bot
    import bot
    datos = bot.llamar("getUpdates")
    for u in reversed(datos.get("result", [])):
        msg = u.get("message") or u.get("channel_post") or {}
        if msg.get("chat", {}).get("id"):
            b["chat"] = str(msg["chat"]["id"])
            return b["chat"]
    print("  apuestas: escribe cualquier cosa al bot de Telegram para que sepa a quién mandar")
    return None


def actualizar(por_dia: dict):
    ahora = datetime.now(TZ)
    b = cargar()
    corregir(b)
    cal = {}
    try:
        import calibracion_auto
        cal = calibracion_auto.tabla(banca=b)
        b["calibracion"] = calibracion_auto.informe(cal)
        for f in b["calibracion"]:
            if f["delta"]:
                print(f"  calibración {f['dep_n']} · {f['mercado']}: {f['n']} picks, previsto {f['prevista']:.0%}, "
                      f"real {f['real']:.0%} -> un 75 % pasa a {f['efecto']:.1%}")
    except Exception as e:  # noqa: BLE001
        print(f"  aviso calibración automática: {e}")
    # A partir de las 22:00 se mandan las del día siguiente; si GitHub se retrasa y ya es de
    # madrugada (o es la primera vez que se arranca el bot), las del mismo día.
    if ahora.hour >= 22:
        dia = ahora.date() + timedelta(days=1)
    elif ahora.hour < 12 or not b.get("ultimo_envio"):
        dia = ahora.date()
    else:
        dia = None
    if dia and (b.get("ultimo_envio") or "") < dia.isoformat():
        pendiente = sum(a["importe"] for a in b["apuestas"] if "ok" not in a and not a.get("previa"))  # dinero aún en juego
        elegidas = elegir(por_dia.get(dia, []), saldo(b) - pendiente, ahora, cal)
        texto = mensaje(elegidas, b, dia)
        print(texto)
        enviado = False
        if config.TELEGRAM_TOKEN:
            chat = _chat(b)
            if chat:
                import bot
                enviado = bool(bot.llamar("sendMessage", chat_id=chat, text=texto, parse_mode="HTML").get("ok"))
        try:  # notificación en la app Android (Firebase)
            import avisos
            if avisos.disponible() and elegidas:
                avisos.enviar(["bot"], f"🟡 Apuestas del {dia:%d/%m}", f"{len(elegidas)} apuestas listas. Toca para verlas.",
                              {"vista": "misap"}, "bot")
        except Exception as e:  # noqa: BLE001
            print(f"  aviso notificación del bot: {e}")
        if config.NTFY_TOPIC:  # notificación al móvil con la app ntfy
            enviado = avisar_ntfy(f"🟡 Apuestas del {dia:%d/%m}", texto) or enviado
        # Se apuntan siempre: si Telegram no está configurado, se ven en la app del bot
        if enviado or not config.TELEGRAM_TOKEN:
            b["ultimo_envio"] = dia.isoformat()
            b["apuestas"] += elegidas
    print(f"  banca: {saldo(b):.2f} € ({len(b['apuestas'])} apuestas)")
    guardar(b)
    return b


def avisar_ntfy(titulo: str, texto_html: str) -> bool:
    """Notificación push al móvil (app gratuita ntfy, tema privado en el secreto NTFY_TOPIC)."""
    import re
    import requests
    plano = re.sub(r"</?(b|i)>", "", texto_html)
    try:
        r = requests.post(f"https://ntfy.sh/{config.NTFY_TOPIC}", data=plano.encode("utf-8"), timeout=30,
                          headers={"Title": titulo.encode("utf-8"), "Tags": "moneybag",
                                   "Click": "https://victormoreno172-sys.github.io/picks-dorados/bot/"})
        return r.ok
    except requests.RequestException as e:
        print(f"  aviso ntfy: {e}")
        return False
