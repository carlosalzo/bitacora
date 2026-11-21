"""Manda el recordatorio diario de Libreta a cada dispositivo que lo activó.

Lee los dispositivos de Firestore (users/{uid}/push/{id}) y manda una
notificación por Firebase Cloud Messaging. Borra los dispositivos que ya no
existen (app desinstalada o permiso quitado).

Necesita el secreto FIREBASE_SERVICE_ACCOUNT (la clave JSON de la cuenta de
servicio del proyecto). Nunca se imprime.
"""
import json
import os
import sys

import google.auth.transport.requests
import requests
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging",
          "https://www.googleapis.com/auth/datastore"]
TITULO = "Libreta"
CUERPO = "¿Cargaste tus gastos de hoy? Anotalos ahora, antes de que se te olviden."


def main():
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        sys.exit("Falta el secreto FIREBASE_SERVICE_ACCOUNT en GitHub.")
    info = json.loads(raw)
    project = info["project_id"]
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    creds.refresh(google.auth.transport.requests.Request())
    h = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents"

    q = {"structuredQuery": {"from": [{"collectionId": "push", "allDescendants": True}]}}
    r = requests.post(base + ":runQuery", headers=h, json=q, timeout=30)
    r.raise_for_status()
    docs = [x["document"] for x in r.json() if "document" in x]
    print(f"Dispositivos: {len(docs)}")

    ok = borrados = errores = 0
    for d in docs:
        token = d.get("fields", {}).get("token", {}).get("stringValue")
        if not token:
            continue
        msg = {"message": {
            "token": token,
            "data": {"title": TITULO, "body": CUERPO, "url": "./?cargar=gasto", "tag": "libreta-recordatorio"},
            "webpush": {"headers": {"Urgency": "high", "TTL": "21600"}},
        }}
        s = requests.post(f"https://fcm.googleapis.com/v1/projects/{project}/messages:send",
                          headers=h, json=msg, timeout=30)
        if s.ok:
            ok += 1
            continue
        status = ""
        try:
            status = s.json().get("error", {}).get("status", "")
        except ValueError:
            pass
        if s.status_code == 404 or status in ("NOT_FOUND", "UNREGISTERED") or \
           (s.status_code == 400 and "registration token" in s.text.lower()):
            requests.delete("https://firestore.googleapis.com/v1/" + d["name"], headers=h, timeout=30)
            borrados += 1
        else:
            errores += 1
            print(f"Error {s.status_code} {status}")
    print(f"Enviados: {ok} · dispositivos dados de baja: {borrados} · errores: {errores}")
    if errores and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
