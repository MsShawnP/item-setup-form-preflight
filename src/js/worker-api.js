/**
 * worker-api — Bridge between UI and validation worker.
 *
 * File parsing, column matching, and schema diffing now run in JS
 * on the main thread (no Pyodide needed). Only validation is
 * delegated to the Pyodide Web Worker.
 */

let worker = null
let messageId = 0
const pending = new Map()

/**
 * Boot the Pyodide Web Worker for validation.
 * Called once at app startup — subsequent calls are no-ops.
 * The worker begins downloading Pyodide immediately in the background.
 */
export function initWorker() {
  if (worker) return

  worker = new Worker(
    new URL('../workers/pyodide-worker.mjs', import.meta.url),
    { type: 'module' },
  )

  worker.addEventListener('message', (event) => {
    const { id, result, error, status } = event.data

    if (status) {
      const store = window.Alpine?.store('app')
      if (!store) return

      store.engineStatus = status
      if (status === 'Ready') {
        store.engineReady = true
      }
      return
    }

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
      store.engineStatus = 'Worker failed to load'
      store.engineError = event.message || 'Unknown worker error'
    }
  })
}

/**
 * Send an action to the Pyodide worker and await its response.
 */
export function sendToWorker(action, data = {}, transferables = []) {
  if (!worker) {
    return Promise.reject(new Error('Worker not initialized'))
  }

  const id = ++messageId

  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    worker.postMessage({ id, action, data }, transferables)
  })
}

/**
 * Run four-tier validation via the Pyodide worker.
 *
 * Sends pre-parsed rows and confirmed mapping to the worker.
 * The worker applies the mapping, loads the schema, and runs
 * validate_product() per row.
 *
 * @param {Object[]} rows - Parsed rows (array of header→value dicts).
 * @param {Object} confirmedMapping - Map of schema field names to uploaded headers.
 * @param {string} partner - Partner key.
 * @returns {Promise<Object>} Per-row results and aggregate summary.
 */
export function validateData(rows, confirmedMapping, partner) {
  // Strip Alpine reactive proxies — proxies can't be structured-cloned for postMessage
  return sendToWorker('validate', {
    rows: JSON.parse(JSON.stringify(rows)),
    confirmedMapping: JSON.parse(JSON.stringify(confirmedMapping)),
    partner,
  })
}
