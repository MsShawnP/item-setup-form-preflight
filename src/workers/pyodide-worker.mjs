const PYODIDE_CDN = 'https://cdn.jsdelivr.net/pyodide/v0.29.4/full/'

let pyodide = null

function postStatus(status) {
  self.postMessage({ status })
}

async function initialize() {
  try {
    postStatus('Downloading Pyodide...')
    const { loadPyodide } = await import(`${PYODIDE_CDN}pyodide.mjs`)

    pyodide = await loadPyodide({
      indexURL: PYODIDE_CDN,
    })

    postStatus('Installing packages...')
    await pyodide.loadPackage('micropip')
    const micropip = pyodide.pyimport('micropip')
    await micropip.install('pydantic==2.10.5')

    postStatus('Ready')
  } catch (err) {
    postStatus(`Failed: ${err.message}`)
  }
}

async function handleMessage(event) {
  const { id, action, data } = event.data

  // Wait for init before processing requests
  if (!pyodide) {
    self.postMessage({ id, error: 'Pyodide not yet initialized' })
    return
  }

  try {
    switch (action) {
      case 'echo': {
        const result = pyodide.runPython(`${data.value} + ${data.value}`)
        self.postMessage({ id, result })
        break
      }
      default:
        self.postMessage({ id, error: `Unknown action: ${action}` })
    }
  } catch (err) {
    self.postMessage({ id, error: err.message })
  }
}

self.addEventListener('message', handleMessage)

initialize()
