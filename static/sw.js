// Bewusst ohne Caching: der Arbeitsplan soll immer aktuell sein.
// Der Service Worker existiert nur, damit die Seite installierbar ist.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
    // Nur GET-Anfragen durchreichen. POST-Formulare (Speichern, Entfernen, ...)
    // werden dem Browser ueberlassen, da abgefangene POST-Weiterleitungen
    // in Safari/iOS zu haengenden Formular-Sends fuehren koennen.
    if (event.request.method !== "GET") {
        return;
    }
    event.respondWith(fetch(event.request));
});
