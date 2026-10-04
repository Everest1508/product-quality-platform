/* PQ Platform service worker. Version: {{ version }}
 *
 * This app is server-rendered and every page is per-user, so pages are never
 * cached. The worker does three things:
 *   1. Shows /offline/ when a page navigation fails.
 *   2. Caches the logo files (cache-first).
 *   3. Caches the CDN scripts and fonts (stale-while-revalidate), so the app
 *      shell still boots on a flaky connection.
 * Non-GET requests (form posts, htmx writes, uploads) always go to the network.
 */
const VERSION = "{{ version }}";
const SHELL = "pq-shell-" + VERSION;
const RUNTIME = "pq-runtime-" + VERSION;
const PRECACHE = [
  "/offline/",
  "/brand/favicon-32.png",
  "/brand/pwa-192.png",
  "/brand/apple-touch-icon.png",
];
const CDN_HOSTS = [
  "unpkg.com",
  "cdn.jsdelivr.net",
  "fonts.googleapis.com",
  "fonts.gstatic.com",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keep = [SHELL, RUNTIME];
      for (const name of await caches.keys()) {
        if (name.startsWith("pq-") && !keep.includes(name)) await caches.delete(name);
      }
      if (self.registration.navigationPreload) await self.registration.navigationPreload.enable();
      await self.clients.claim();
    })()
  );
});

async function staleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME);
  const cached = await cache.match(request);
  const refresh = fetch(request)
    .then((response) => {
      if (response && (response.ok || response.type === "opaque")) cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached || refresh;
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) (await caches.open(SHELL)).put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  if (request.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          const preload = await event.preloadResponse;
          return preload || (await fetch(request));
        } catch (err) {
          return (await caches.match("/offline/")) || Response.error();
        }
      })()
    );
    return;
  }

  if (url.origin === self.location.origin) {
    if (url.pathname.startsWith("/brand/")) event.respondWith(cacheFirst(request));
    return;
  }

  if (CDN_HOSTS.includes(url.hostname)) event.respondWith(staleWhileRevalidate(request));
});
