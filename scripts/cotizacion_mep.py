"""Actualiza cotiz.json con el dólar MEP (bolsa), precio de venta.

Fuente principal: dolarapi.com (valor del día).
Historial: api.argentinadatos.com (cierres diarios), para poder convertir
movimientos de fechas pasadas con el MEP de ese día.

Sale con error si no puede leer un valor confiable, así no se guarda nada raro
y GitHub avisa por mail que la tarea falló.
"""
import datetime as dt
import json
import sys
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
HOY_URL = "https://dolarapi.com/v1/dolares/bolsa"
HIST_URL = "https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "libreta-app (GitHub Actions)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def valido(v):
    return isinstance(v, (int, float)) and 100 < v < 1_000_000


def main():
    hoy = dt.datetime.now(TZ).date()
    with open("cotiz.json", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("tipo") != "MEP":  # antes guardaba BNA divisa: arrancamos el historial de cero
        data = {"tipo": "MEP", "hist": {}}

    errores = []
    # Historial de cierres (últimos 400 días)
    try:
        desde = (hoy - dt.timedelta(days=400)).isoformat()
        for row in get_json(HIST_URL):
            f, v = str(row.get("fecha", ""))[:10], row.get("venta")
            if f >= desde and valido(v):
                data["hist"][f] = round(float(v), 2)
    except Exception as e:
        errores.append(f"historial: {e}")

    # Valor del día
    ultima = None
    try:
        d = get_json(HOY_URL)
        v, c = d.get("venta"), d.get("compra")
        f = dt.datetime.fromisoformat(str(d.get("fechaActualizacion")).replace("Z", "+00:00")).astimezone(TZ).date()
        if valido(v) and (hoy - f).days <= 7:
            ultima = {"fecha": f.isoformat(), "venta": round(float(v), 2), "compra": round(float(c), 2) if valido(c) else None}
            data["hist"][f.isoformat()] = ultima["venta"]
        else:
            errores.append(f"valor del día fuera de rango o viejo: {v} del {f}")
    except Exception as e:
        errores.append(f"valor del día: {e}")

    if not ultima and data["hist"]:
        f = max(data["hist"])
        if (hoy - dt.date.fromisoformat(f)).days <= 7:
            ultima = {"fecha": f, "venta": data["hist"][f], "compra": None}
    if not ultima:
        sys.exit("No se pudo leer el dólar MEP. " + " | ".join(errores))

    ultima["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    data["fuente"] = "Dólar MEP (bolsa), venta"
    data["ultima"] = ultima
    data["hist"] = dict(sorted(data["hist"].items()))
    with open("cotiz.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"MEP {ultima['fecha']}: venta {ultima['venta']} · {len(data['hist'])} días en el historial"
          + (f" · avisos: {' | '.join(errores)}" if errores else ""))


if __name__ == "__main__":
    main()
