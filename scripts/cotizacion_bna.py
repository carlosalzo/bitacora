"""Lee el dólar BNA (tabla Divisas, Dolar U.S.A) de bna.com.ar y actualiza cotiz.json.

Sale con error si no puede leer un valor confiable, así no se guarda nada raro
y GitHub avisa por mail que la tarea falló.
"""
import datetime as dt
import json
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo

URLS = ["https://www.bna.com.ar/Personas", "https://www.bna.com.ar/"]
TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def numero(txt):
    txt = txt.strip()
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    return float(txt)


def leer(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "es-AR,es;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def extraer(html):
    i = html.find('id="divisas"')
    if i < 0:
        m = re.search(r">\s*Divisas\s*<", html, re.I)
        if not m:
            raise ValueError("no encontré la tabla Divisas")
        i = m.start()
    tramo = html[i:i + 8000]
    fila = re.search(r"Dolar\s+U\.?\s*S\.?\s*A\.?\s*</td>\s*<td[^>]*>\s*([\d.,]+)\s*</td>\s*<td[^>]*>\s*([\d.,]+)\s*</td>",
                     tramo, re.I | re.S)
    if not fila:
        raise ValueError("no encontré la fila Dolar U.S.A en Divisas")
    f = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", tramo)
    if not f:
        raise ValueError("no encontré la fecha de la tabla")
    fecha = dt.date(int(f.group(3)), int(f.group(2)), int(f.group(1)))
    return fecha, numero(fila.group(1)), numero(fila.group(2))


def main():
    errores = []
    for url in URLS:
        try:
            fecha, compra, venta = extraer(leer(url))
            break
        except Exception as e:  # probamos la otra página
            errores.append(f"{url}: {e}")
    else:
        sys.exit("No se pudo leer la cotización. " + " | ".join(errores))

    hoy = dt.datetime.now(TZ).date()
    if not (100 < venta < 1_000_000) or compra > venta:
        sys.exit(f"Valores fuera de rango: compra {compra}, venta {venta}")
    if fecha > hoy or (hoy - fecha).days > 7:
        sys.exit(f"Fecha sospechosa en la tabla: {fecha}")

    with open("cotiz.json", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("hist", {})[fecha.isoformat()] = venta
    data["hist"] = dict(sorted(data["hist"].items()))
    data["ultima"] = {"fecha": fecha.isoformat(), "compra": compra, "venta": venta,
                      "actualizado": dt.datetime.now(TZ).isoformat(timespec="minutes")}
    with open("cotiz.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"BNA divisa {fecha}: compra {compra} / venta {venta}")


if __name__ == "__main__":
    main()
