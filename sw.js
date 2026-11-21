// Libreta: guarda la app en el celu para que abra sin señal.
// Los datos los maneja Firestore aparte (tiene su propia caché), acá solo va la app.
const CACHE = "libreta-v17";
const APP = ["./", "index.html", "manifest.webmanifest", "cotiz.json",
  "icons/icon-192-libreta.png", "icons/icon-512-libreta.png", "icons/maskable-512-libreta.png", "icons/apple-touch-icon-libreta.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(APP)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const sameOrigin = u => u.origin === self.location.origin;
const isLib = u => (u.hostname === "www.gstatic.com" && u.pathname.startsWith("/firebasejs/"))
  || u.hostname === "fonts.googleapis.com" || u.hostname === "fonts.gstatic.com";

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (sameOrigin(url)) {
    // Primero la red (para tener siempre la última versión y cotización); sin señal, lo guardado.
    e.respondWith(fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(url.pathname.endsWith("cotiz.json") ? "cotiz.json" : req, copy)); }
      return res;
    }).catch(async () => {
      if (url.pathname.endsWith("cotiz.json")) return caches.match("cotiz.json");
      return (await caches.match(req)) || (req.mode === "navigate" ? caches.match("index.html") : undefined) || Response.error();
    }));
  } else if (isLib(url)) {
    // Librerías y fuentes: no cambian, se usan desde la caché.
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
  }
});

// Recordatorio diario: llega por Firebase Cloud Messaging y se muestra acá.
self.addEventListener("push", e => {
  let p = {};
  try { p = e.data ? e.data.json() : {}; } catch (_) { p = { data: { body: e.data && e.data.text() } }; }
  const d = Object.assign({}, p.notification || {}, p.data || {});
  e.waitUntil(self.registration.showNotification(d.title || "Libreta", {
    body: d.body || "¿Cargaste tus gastos de hoy?",
    icon: "icons/icon-192-libreta.png",
    badge: "icons/icon-192-libreta.png",
    tag: d.tag || "libreta-recordatorio",
    renotify: true,
    data: { url: d.url || "./?cargar=gasto" }
  }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "./", self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(cs => {
    const c = cs.find(x => x.url.startsWith(self.registration.scope));
    if (c) return c.navigate(url).then(w => (w || c).focus()).catch(() => c.focus());
    return self.clients.openWindow(url);
  }));
});
