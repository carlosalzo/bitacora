# Bitácora

App personal para el celu: gastos e ingresos (pesos y dólares), pendientes de cobro, resumen con gráficos y services de vehículos.

- **App:** https://carlosalzo.github.io/bitacora/
- **Datos:** Firebase (inicio de sesión con Google + Firestore). Cada usuario solo ve lo suyo.
- **Cotización:** `cotiz.json`, BNA divisa venta, actualizada los días hábiles por GitHub Actions (`.github/workflows/publicar.yml`).
- **Sin conexión:** `sw.js` guarda la app en el celu; Firestore guarda los datos y los sube al volver la señal.

## Instalar
- **Android (Chrome):** abrir la app → menú ⋮ → *Instalar app*.
- **iPhone (Safari):** abrir la app → Compartir → *Agregar a inicio*.
