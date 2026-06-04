let worker = null
let messageId = 0
const pending = new Map()

/**
 * Boot the Pyodide Web Worker and wire up message handling.
 * Called once at app startup — subsequent calls are no-ops.
 */
export function initWorker() {
  if (worker) return

  worker = new Worker(
    new URL('../workers/pyodide-worker.mjs', import.meta.url),
    { type: 'module' },
  )

  worker.addEventListener('message', (event) => {
    const { id, result, error, status } = event.data

    // Status broadcasts (no id) update the Alpine store directly
    if (status) {
      const store = window.Alpine?.store('app')
      if (!store) return

      store.loadingStatus = status
      if (status === 'Ready') {
        store.pyodideReady = true
      }
      return
    }

    // Correlated responses resolve/reject the matching promise
    const entry = pending.get(id)
    if (!entry) return
    pending.delete(id)

    if (error) {
      entry.reject(new Error(error))
    } else {
      entry.resolve(result)
    }
  })

  worker.addEventListener('error', (event) => {
    const store = window.Alpine?.store('app')
    if (store) {
      store.loadingStatus = 'Worker failed to load'
      store.loadingError = event.message || 'Unknown worker error'
    }
  })
}

/**
 * Send an action to the Pyodide worker and await its response.
 * Returns a promise that resolves with the worker's result payload
 * or rejects with an Error if the worker reports a failure.
 */
export function sendToWorker(action, data = {}) {
  if (!worker) {
    return Promise.reject(new Error('Worker not initialized'))
  }

  const id = ++messageId

  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    worker.postMessage({ id, action, data })
  })
}
