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
 *
 * @param {string} action - The action name for the worker to handle.
 * @param {object} data - Payload for the action.
 * @param {Transferable[]} [transferables] - Optional list of transferable
 *   objects (e.g. ArrayBuffer) for zero-copy transfer to the worker.
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
 * Parse a file and match its columns against a partner schema.
 *
 * Sends the file ArrayBuffer to the worker using zero-copy transfer.
 * The ArrayBuffer is neutered after this call — do not reuse it.
 *
 * @param {ArrayBuffer} file - Raw file bytes.
 * @param {string} filename - Original filename (for extension detection).
 * @param {string} partner - Partner key (walmart|costco|unfi|kehe).
 * @returns {Promise<object>} Mapping result with matched/unmatched columns.
 */
export function matchColumns(file, filename, partner) {
  return sendToWorker('match', { file, filename, partner }, [file])
}

/**
 * Run four-tier validation using a confirmed column mapping.
 *
 * Operates on the file data cached in the worker from the most
 * recent matchColumns call.
 *
 * @param {object} confirmedMapping - Map of schema field names to uploaded headers.
 * @param {string} partner - Partner key.
 * @returns {Promise<object>} Per-row results and aggregate summary.
 */
export function validateData(confirmedMapping, partner) {
  return sendToWorker('validate', { confirmedMapping, partner })
}
