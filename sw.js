/* Curiculy service worker: the app shell cache.

Offline writes are queued and replayed by the page (static/js/app.js), not
here: replay needs the current sign-in, and a service worker cannot read it
without storing a token where it would outlive logout.

SHELL_VERSION is the one cache-bust token. index.html and CSS query strings
must use the same value. Changing it also renames SHELL_CACHE so activate()
drops the previous shell instead of mixing old and new URLs.
*/
const SHELL_VERSION = "20261010-greeting";
const SHELL_CACHE = `curiculy-shell-${SHELL_VERSION}`;
const SHELL_URLS = [
  "/",
  `/static/js/theme-boot.js?v=${SHELL_VERSION}`,
  `/static/js/app.js?v=${SHELL_VERSION}`,
  `/static/vendor/chartjs-4.5.1/chart.umd.min.js?v=${SHELL_VERSION}`,
  `/static/css/tokens.css?v=${SHELL_VERSION}`,
  `/static/css/app.css?v=${SHELL_VERSION}`,
  `/static/fonts/figtree-latin-wght.woff2?v=${SHELL_VERSION}`,
  `/static/fonts/newsreader-latin-wght.woff2?v=${SHELL_VERSION}`,
  `/static/fonts/newsreader-latin-wght-italic.woff2?v=${SHELL_VERSION}`,
  `/static/fonts/fredoka-latin-wght.woff2?v=${SHELL_VERSION}`,
  `/static/fonts/nunito-latin-wght.woff2?v=${SHELL_VERSION}`,
  `/static/curiculy-logo.png?v=${SHELL_VERSION}`,
  `/static/night-mountains.jpg?v=${SHELL_VERSION}`,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      await cache.addAll(SHELL_URLS);
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key !== SHELL_CACHE).map((key) => caches.delete(key)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === "/api" || url.pathname.startsWith("/api/")) return;
  if (url.pathname.startsWith("/evidence/")) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.mode === "navigate") {
          const shell = await caches.match("/");
          if (shell) return shell;
        }
        return Response.error();
      })
  );
});
