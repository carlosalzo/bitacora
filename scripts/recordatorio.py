"""Manda el recordatorio diario de Libreta a cada dispositivo que lo activó, a su hora.

Corre cada hora. A cada dispositivo le manda el aviso si ya es su hora (o faltan
menos de 20 minutos) y todavía no se lo mandó hoy; así una demora de GitHub no
hace que se pierda ni que llegue dos veces.

Lee los dispositivos de Firestore (users/{uid}/push/{id}) y manda una
notificación por Firebase Cloud Messaging. Borra los dispositivos que ya no
existen (app desinstalada o permiso quitado).

Necesita el secreto FIREBASE_SERVICE_ACCOUNT (la clave JSON de la cuenta de
servicio del proyecto). Nunca se imprime.
"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import google.auth.transport.requests
import requests
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging",
          "https://www.googleapis.com/auth/datastore"]
TITULO = "Libreta"
CUERPO = "¿Cargaste tus gastos de hoy? Anotalos ahora, antes de que se te olviden."
TZ = ZoneInfo("America/Argentina/Buenos_Aires")
ANTES = dt.timedelta(minutes=20)    # puede llegar hasta 20 min antes
DESPUES = dt.timedelta(minutes=100) # si GitHub se demora, todavía se manda


def toca(hora, ahora, enviado, forzar):
    """Devuelve el día del aviso que le toca ahora (AAAA-MM-DD), o None si no le toca."""
    if forzar:
        return ahora.date().isoformat()
    try:
        h, m = (int(x) for x in (hora or "21:00").split(":"))
    except ValueError:
        h, m = 21, 0
    objetivo = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    for o in (objetivo, objetivo - dt.timedelta(days=1)):  # cubre horarios cerca de medianoche
        if o - ANTES <= ahora <= o + DESPUES:
            dia = o.date().isoformat()
            return dia if enviado != dia else None
    return None


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
    print(f"Dispositivos registrados: {len(docs)}")

    ahora = dt.datetime.now(TZ)
    forzar = os.environ.get("FORZAR", "") == "true"
    ok = borrados = errores = 0
    for d in docs:
        f = d.get("fields", {})
        token = f.get("token", {}).get("stringValue")
        hora = f.get("hora", {}).get("stringValue", "21:00")
        enviado = f.get("enviado", {}).get("stringValue", "")
        dia = toca(hora, ahora, enviado, forzar) if token else None
        if not dia:
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
            if forzar:  # una prueba no cuenta como el aviso del día
                continue
            requests.patch("https://firestore.googleapis.com/v1/" + d["name"],
                           params={"updateMask.fieldPaths": "enviado"}, headers=h,
                           json={"fields": {"enviado": {"stringValue": dia}}}, timeout=30)
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
