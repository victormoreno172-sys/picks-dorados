"""Prueba temporal del ranking online: sesión anónima, escribir, leer y borrar (sin publicar claves)."""
import json, os, requests, online
out = {}
cfg = online.config_app() or {}
K, P = cfg.get("apiKey"), cfg.get("projectId"); out["config"] = bool(K)
r = requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={K}", json={"returnSecureToken": True}, timeout=30)
out["anonimo"] = r.status_code; j = r.json() if r.ok else {}; out["anon_err"] = None if r.ok else r.text[:200]
if r.ok:
    tok, uid = j["idToken"], j["localId"]; H = {"Authorization": "Bearer " + tok}
    B = f"https://firestore.googleapis.com/v1/projects/{P}/databases/(default)/documents"
    doc = {"fields": {"n": {"stringValue": "PruebaBot"}, "nl": {"stringValue": "pruebabot"}, "nv": {"integerValue": "1"}, "t": {"integerValue": "1"}}}
    w = requests.patch(f"{B}/jugadores/{uid}", headers=H, json=doc, timeout=30); out["escribir"] = w.status_code; out["esc_err"] = None if w.ok else w.text[:200]
    mal = requests.patch(f"{B}/jugadores/otro_uid_cualquiera", headers=H, json=doc, timeout=30); out["escribir_ajeno (debe ser 403)"] = mal.status_code
    l = requests.get(f"{B}/jugadores?pageSize=50", headers=H, timeout=30); out["leer"] = l.status_code; out["n_fichas"] = len(l.json().get("documents", [])) if l.ok else None
    d = requests.delete(f"{B}/jugadores/{uid}", headers=H, timeout=30); out["borrar"] = d.status_code
json.dump(out, open("resultado.json", "w"), ensure_ascii=False, indent=1)
