/* Curiculy service worker: app shell cache + IndexedDB outbox replay. */

const SHELL_CACHE = "curiculy-shell-v20";
const SHELL_URLS = [
  "/",
  "/static/js/app.js?v=20260828-widget-hug",
  "/static/css/app.css?v=20260828-widget-hug",
  "/static/curiculy-logo.png?v=20260826-new-logo",
];

const SYNC_DB_NAME = "curiculy-sync";
const SYNC_DB_VERSION = 1;
const OUTBOX_STORE = "outbox";

function openSyncDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(SYNC_DB_NAME, SYNC_DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(OUTBOX_STORE)) {
        db.createObjectStore(OUTBOX_STORE, { keyPath: "id", autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("IndexedDB open failed"));
  });
}

function idbReq(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function idbTxDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

async function outboxAll() {
  const db = await openSyncDb();
  try {
    return await idbReq(db.transaction(OUTBOX_STORE, "readonly").objectStore(OUTBOX_STORE).getAll());
  } finally {
    db.close();
  }
}

async function outboxDelete(id) {
  const db = await openSyncDb();
  try {
    const tx = db.transaction(OUTBOX_STORE, "readwrite");
    tx.objectStore(OUTBOX_STORE).delete(id);
    await idbTxDone(tx);
  } finally {
    db.close();
  }
}

function restoreRequestBody(record) {
  if (record.bodyKind === "formdata") {
    const form = new FormData();
    for (const part of record.body || []) {
      if (part.kind === "blob") {
        form.append(part.name, part.blob, part.filename || "file");
      } else {
        form.append(part.name, part.value);
      }
    }
    return form;
  }
  if (record.bodyKind === "urlencoded" || record.bodyKind === "text") {
    return record.body;
  }
  if (record.bodyKind === "blob") {
    return record.body;
  }
  return undefined;
}

function replayHeaders(record) {
  const headers = { ...(record.headers || {}) };
  if (record.bodyKind === "formdata") {
    delete headers["Content-Type"];
    delete headers["content-type"];
  }
  return headers;
}

async function flushOutbox() {
  const items = await outboxAll();
  let incomplete = false;
  for (const item of items) {
    try {
      const response = await fetch(item.url, {
        method: item.method,
        headers: replayHeaders(item),
        body: restoreRequestBody(item),
      });
      if (response.ok) {
        await outboxDelete(item.id);
        continue;
      }
      incomplete = true;
    } catch {
      incomplete = true;
    }
  }
  if (incomplete) {
    throw new Error("Outbox sync incomplete");
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      await Promise.all(SHELL_URLS.map((url) => cache.add(url).catch(() => {})));
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

self.addEventListener("sync", (event) => {
  if (event.tag === "sync-outbox") {
    event.waitUntil(flushOutbox());
  }
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "sync-outbox") {
    event.waitUntil(flushOutbox());
  }
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
