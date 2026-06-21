const CACHE_VERSION = 'preflight-v1'
const PYODIDE_VERSION = 'v0.29.4'
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`

self.addEventListener('install', (event) => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_VERSION)
          .map((key) => caches.delete(key)),
      ),
    ).then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Pyodide CDN assets (WASM, JS loader, packages) — cache-first
  if (url.origin === 'https://cdn.jsdelivr.net' && url.pathname.includes('/pyodide/')) {
    event.respondWith(cacheFirst(event.request))
    return
  }

  // Hashed static assets (Vite output: /assets/*.js, /assets/*.css) — cache-first
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(event.request))
    return
  }

  // Fonts — cache-first
  if (url.pathname.startsWith('/fonts/')) {
    event.respondWith(cacheFirst(event.request))
    return
  }

  // HTML pages — network-first so deploys propagate
  if (event.request.mode === 'navigate' || event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirst(event.request))
    return
  }
})

async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached

  const response = await fetch(request)
  if (response.ok) {
    const cache = await caches.open(CACHE_VERSION)
    cache.put(request, response.clone())
  }
  return response
}

async function networkFirst(request) {
  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(CACHE_VERSION)
      cache.put(request, response.clone())
    }
    return response
  } catch {
    const cached = await caches.match(request)
    if (cached) return cached
    throw new Error('Network unavailable and no cache')
  }
}
