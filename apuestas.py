"""
Bot de apuestas: cada noche (hacia las 23:35 de Madrid) elige las apuestas del día siguiente con
las reglas del Top y manda por Telegram la lista con el importe de cada una para la banca real.
Las apuestas se apuntan en historial/banca.json y se corrigen solas con los resultados reales,
así el mensaje lleva siempre el saldo al día (suponiendo que se han hecho todas a esa cuota).

Reglas:
  - probabilidad >= 70 % y cuota de la casa (real o estimada ≈) >= 1.30
  - solo con valor: probabilidad × cuota − 1 >= 2 % (cuota real) o >= 4 % (cuota ≈)
  - un pick por partido; como mucho 8 apuestas y un 15 % de la banca en un día
  - importe: un cuarto de Kelly, entre el 0,5 % y el 3 % de la banca (la mitad si la cuota es ≈)
  - de momento fútbol y basket (son los que se pueden corregir solos con el resultado)
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import config
import historial

RUTA = os.path.join(os.path.dirname(historial.RUTA), "banca.json")
TZ = ZoneInfo(config.ZONA_HORARIA)
PROB_MIN, CUOTA_MIN = 0.70, 1.30
VALOR_REAL, VALOR_APROX = 0.02, 0.04
MAX_APUESTAS, MAX_EXPOSICION = 8, 0.15


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


def saldo(b: dict) -> float:
    s = b["inicial"]
    for a in b["apuestas"]:
        if a.get("ok") is True:
            s += a["importe"] * (a["cuota"] - 1)
        elif a.get("ok") is False:
            s -= a["importe"]
    return round(s, 2)


def corregir(b: dict):
    for a in b["apuestas"]:
        if "ok" in a:
            continue
        f = date.fromisoformat(a["fecha"])
        for d in (f, f - timedelta(days=1), f + timedelta(days=1)):
            res = historial.RESULTADOS.get((d.isoformat(), a["local"], a["visitante"]))
            if res:
                ok = historial.acierta(a["mercado"], *res)
                if ok is not None:
                    a["ok"], a["res"] = ok, list(res)
                break
        else:
            if (date.today() - f).days > 10:  # aplazado: se devuelve el dinero
                a["ok"] = None


def _deporte(a) -> str:
    return a.partido.deporte or ("b" if config.es_baloncesto(a.partido.liga) else "f")


def elegir(lista, banca: float, ahora: datetime) -> list[dict]:
    candidatas = []
    for a in lista:
        if _deporte(a) not in ("f", "b"):
            continue
        p = a.partido
        if p.hora and p.fecha == ahora.date() and p.hora <= ahora.strftime("%H:%M"):
            continue  # ya ha empezado
        mejor = None
        for k in a.picks:
            if not k.cuota or k.prob < PROB_MIN or k.cuota < CUOTA_MIN:
                continue
            ev = k.prob * k.cuota - 1
            if ev < (VALOR_APROX if k.estimada else VALOR_REAL):
                continue
            if mejor is None or ev > mejor[0]:
                mejor = (ev, k)
        if mejor:
            ev, k = mejor
            kelly = ev / (k.cuota - 1) / 4
            frac = min(0.03, max(0.005, kelly)) * (0.5 if k.estimada else 1)
            candidatas.append({"fecha": p.fecha.isoformat(), "hora": p.hora, "liga": p.liga,
                               "local": p.local, "visitante": p.visitante, "mercado": k.mercado,
                               "prob": round(float(k.prob), 3), "cuota": float(k.cuota),
                               "estimada": bool(k.estimada), "ev": round(ev, 3),
                               "importe": max(0.5, round(banca * frac * 2) / 2)})
    candidatas.sort(key=lambda c: -c["ev"])
    elegidas, gastado = [], 0.0
    for c in candidatas[:MAX_APUESTAS]:
        if gastado + c["importe"] > banca * MAX_EXPOSICION:
            break
        elegidas.append(c)
        gastado += c["importe"]
    return sorted(elegidas, key=lambda c: c["hora"] or "99")


def _ayer(b: dict, dia: date) -> str:
    ayer = (dia - timedelta(days=1)).isoformat()
    hechas = [a for a in b["apuestas"] if a["fecha"] == ayer and a.get("ok") in (True, False)]
    if not hechas:
        return ""
    neto = sum(a["importe"] * (a["cuota"] - 1) if a["ok"] else -a["importe"] for a in hechas)
    lineas = [f"{'✅' if a['ok'] else '❌'} {a['local']} – {a['visitante']}: {a['mercado']}" for a in hechas]
    return (f"📋 <b>Ayer</b>: {sum(a['ok'] for a in hechas)}/{len(hechas)} acertadas, "
            f"{neto:+.2f} €\n" + "\n".join(lineas) + "\n")


def mensaje(elegidas: list[dict], b: dict, hoy: date) -> str:
    s = saldo(b)
    cerradas = [a for a in b["apuestas"] if a.get("ok") in (True, False)]
    ganadas = sum(1 for a in cerradas if a["ok"])
    t = [_ayer(b, hoy) + f"🟡 <b>Apuestas del {hoy:%d/%m}</b>\n"]
    if elegidas:
        for c in elegidas:
            casa = "≈ " if c["estimada"] else ""
            t.append(f"⏰ {c['hora'] or '?'} · {config.nombre_liga(c['liga'])}\n"
                     f"<b>{c['local']} – {c['visitante']}</b>\n"
                     f"👉 {c['mercado']} · {c['prob']:.0%} · cuota {casa}{c['cuota']:.2f} · "
                     f"<b>{c['importe']:.2f} €</b> (+{c['ev']:.0%})\n")
        t.append(f"Total del día: <b>{sum(c['importe'] for c in elegidas):.2f} €</b>")
        if any(c["estimada"] for c in elegidas):
            t.append("≈ = cuota estimada: apuesta solo si en Winamax pagan eso o más.")
    else:
        t.append("Hoy no hay apuestas con valor (70 %+ y bien pagadas). Mejor no apostar.")
    t.append(f"\n💰 Banca: <b>{s:.2f} €</b> (empezó con {b['inicial']:.0f} €, "
             f"{s / b['inicial'] - 1:+.1%})" + (f" · {ganadas}/{len(cerradas)} acertadas" if cerradas else ""))
    t.append("<i>Importes para una banca de "
             f"{s:.0f} €. Juega con responsabilidad. +18.</i>")
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
    # A partir de las 22:00 se mandan las del día siguiente; si GitHub se retrasa y ya es de
    # madrugada (o es la primera vez que se arranca el bot), las del mismo día.
    if ahora.hour >= 22:
        dia = ahora.date() + timedelta(days=1)
    elif ahora.hour < 12 or not b.get("ultimo_envio"):
        dia = ahora.date()
    else:
        dia = None
    if dia and (b.get("ultimo_envio") or "") < dia.isoformat():
        elegidas = elegir(por_dia.get(dia, []), saldo(b), ahora)
        texto = mensaje(elegidas, b, dia)
        print(texto)
        enviado = False
        if config.TELEGRAM_TOKEN:
            chat = _chat(b)
            if chat:
                import bot
                enviado = bool(bot.llamar("sendMessage", chat_id=chat, text=texto, parse_mode="HTML").get("ok"))
        if enviado:  # solo cuentan las apuestas que de verdad te han llegado
            b["ultimo_envio"] = dia.isoformat()
            b["apuestas"] += elegidas
    print(f"  banca: {saldo(b):.2f} € ({len(b['apuestas'])} apuestas)")
    guardar(b)
    return b
