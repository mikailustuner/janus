/*
 * Janus service worker (experience design §13.4, DP22). Hand-written and small:
 * - never caches /api (medical results are never served from a cache, Req 22.5);
 * - precaches the demo routes of the five languages, the doctor page and the PDF fonts at install;
 * - cache-first for /_next/static (immutable), stale-while-revalidate for other same-origin GETs
 *   (pages, RSC payloads, the demo fixture and vocabulary chunks), so the demo works offline
 *   after one visit (Req 4.4). "Delete everything" removes every cache whose name starts with janus.
 */
const VERSION = new URL(self.location.href).searchParams.get("v") || "dev";
const CACHE = `janus-${VERSION}`;
const LOCALES = ["en", "tr", "de", "fr", "es"];
const ROUTES = [
  "",
  "/demo",
  "/demo/codes",
  "/demo/doctor",
  "/medicines",
  "/timeline",
  "/results",
  "/results/finding",
  "/memory",
  "/note",
  "/settings",
  "/research",
  "/research/seance",
];
const PRECACHE = [
  ...LOCALES.flatMap((l) => ROUTES.map((r) => `/${l}${r}`)),
  "/o",
  "/fonts/AtkinsonHyperlegibleNext-Regular.ttf",
  "/fonts/AtkinsonHyperlegibleNext-Bold.ttf",
  "/fonts/Fraunces-SemiBold.ttf",
  "/fonts/IBMPlexMono-Regular.ttf",
  "/fonts/NotoSans-Fallback.ttf",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) =>
        Promise.all(
          PRECACHE.map((url) =>
            cache
              .add(new Request(url, { credentials: "omit" }))
              .catch(() => undefined),
          ),
        ),
      ),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((n) => n.startsWith("janus-") && n !== CACHE)
            .map((n) => caches.delete(n)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // network only, never cached
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) caches.open(CACHE).then((c) => c.put(req, res.clone()));
            return res;
          }),
      ),
    );
    return;
  }
  event.respondWith(
    caches.open(CACHE).then((cache) =>
      cache.match(req, { ignoreSearch: false }).then((hit) => {
        const network = fetch(req)
          .then((res) => {
            if (res.ok && res.type === "basic") cache.put(req, res.clone());
            return res;
          })
          .catch(() => hit || caches.match(url.pathname));
        return hit || network;
      }),
    ),
  );
});

// Zombie Alert (zombie-alert Req 4.4, DP5): a click on the local notification opens the note.
// The page shows the notification; the worker never checks in the background (DP4).
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const raw = event.notification.data && event.notification.data.url;
  const url =
    typeof raw === "string" && /^\/(en|tr|de|fr|es)\/note$/.test(raw)
      ? raw
      : "/";
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((list) => {
        const open = list.find(
          (c) => new URL(c.url).origin === self.location.origin,
        );
        return open
          ? open.navigate(url).then((c) => (c || open).focus())
          : self.clients.openWindow(url);
      }),
  );
});
