// Bewusst ohne Caching: der Arbeitsplan soll immer aktuell sein.
// Der Service Worker existiert nur, damit die Seite installierbar ist.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
    event.respondWith(fetch(event.request));
});
