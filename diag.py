import json, os
out = {}
a = os.environ.get("FIREBASE_APP", "")
c = os.environ.get("FIREBASE_CUENTA", "")
out["app_len"], out["cuenta_len"] = len(a), len(c)
try:
    j = json.loads(a)
    out["app_ok"] = True
    out["app_proyecto"] = j.get("project_info", {}).get("project_id")
    out["app_paquetes"] = [cl.get("client_info", {}).get("android_client_info", {}).get("package_name") for cl in j.get("client", [])]
except Exception as e:
    out["app_ok"] = f"no: {e}"
try:
    k = json.loads(c)
    out["cuenta_ok"] = True
    out["cuenta_tipo"], out["cuenta_proyecto"] = k.get("type"), k.get("project_id")
    out["tiene_clave"] = "private_key" in k
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    cr = service_account.Credentials.from_service_account_info(k, scopes=["https://www.googleapis.com/auth/firebase.messaging"])
    cr.refresh(Request())
    import requests
    r = requests.post(f"https://fcm.googleapis.com/v1/projects/{k['project_id']}/messages:send",
                      headers={"Authorization": f"Bearer {cr.token}"},
                      json={"validate_only": True, "message": {"topic": "prueba", "notification": {"title": "Prueba", "body": "ok"}}}, timeout=30)
    out["envio_prueba"] = [r.status_code, r.text[:300]]
except Exception as e:
    out["cuenta_ok"] = f"no: {type(e).__name__}: {str(e)[:200]}"
json.dump(out, open("resultado.json", "w"), indent=1)
