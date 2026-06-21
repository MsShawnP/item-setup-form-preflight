/**
 * Pyodide Web Worker — validation only.
 *
 * File parsing, column matching, and schema diffing now run in JS
 * on the main thread. This worker handles only the four-tier
 * validation engine (Pydantic models + GTIN check digit), which
 * requires Python/Pyodide.
 */

const PYODIDE_CDN = 'https://cdn.jsdelivr.net/pyodide/v0.29.4/full/'

// Import Python source files as raw strings (Vite ?raw imports)
import engineInit from '../engine/__init__.py?raw'
import modelsCode from '../engine/models.py?raw'
import validatorsCode from '../engine/validators.py?raw'
import schemaLoaderCode from '../engine/schema_loader.py?raw'
import orchestratorCode from '../engine/orchestrator.py?raw'
import gtinInit from '../engine/gtin/__init__.py?raw'
import gtinCoreCode from '../engine/gtin/gtin_core.py?raw'

// Import YAML schemas as raw strings
import walmartYaml from '../schemas/walmart.yaml?raw'
import costcoYaml from '../schemas/costco.yaml?raw'
import unfiYaml from '../schemas/unfi.yaml?raw'
import keheYaml from '../schemas/kehe.yaml?raw'

let pyodide = null

function postStatus(status) {
  self.postMessage({ status })
}

function rewriteImports(source) {
  return source.replace(/from src\.engine\./g, 'from engine.')
}

async function initialize() {
  try {
    postStatus('Downloading validation engine...')
    const { loadPyodide } = await import(`${PYODIDE_CDN}pyodide.mjs`)

    pyodide = await loadPyodide({
      indexURL: PYODIDE_CDN,
    })

    postStatus('Loading packages...')
    await pyodide.loadPackage(['pyyaml'])

    postStatus('Starting engine...')

    // Write Python engine to Pyodide virtual filesystem
    pyodide.FS.mkdirTree('/home/pyodide/engine/gtin')

    pyodide.FS.writeFile('/home/pyodide/engine/__init__.py', rewriteImports(engineInit))
    pyodide.FS.writeFile('/home/pyodide/engine/models.py', rewriteImports(modelsCode))
    pyodide.FS.writeFile('/home/pyodide/engine/validators.py', rewriteImports(validatorsCode))
    pyodide.FS.writeFile('/home/pyodide/engine/schema_loader.py', rewriteImports(schemaLoaderCode))
    pyodide.FS.writeFile('/home/pyodide/engine/orchestrator.py', rewriteImports(orchestratorCode))
    pyodide.FS.writeFile('/home/pyodide/engine/gtin/__init__.py', rewriteImports(gtinInit))
    pyodide.FS.writeFile('/home/pyodide/engine/gtin/gtin_core.py', rewriteImports(gtinCoreCode))

    // Write YAML schemas
    pyodide.FS.mkdirTree('/home/pyodide/schemas')
    pyodide.FS.writeFile('/home/pyodide/schemas/walmart.yaml', walmartYaml)
    pyodide.FS.writeFile('/home/pyodide/schemas/costco.yaml', costcoYaml)
    pyodide.FS.writeFile('/home/pyodide/schemas/unfi.yaml', unfiYaml)
    pyodide.FS.writeFile('/home/pyodide/schemas/kehe.yaml', keheYaml)

    // Add engine root to Python path
    pyodide.runPython('import sys; sys.path.insert(0, "/home/pyodide")')

    // Verify the engine loads
    pyodide.runPython('from engine.orchestrator import do_validate')

    postStatus('Ready')
  } catch (err) {
    postStatus(`Failed: ${err.message}`)
  }
}

async function handleMessage(event) {
  const { id, action, data } = event.data

  if (!pyodide) {
    self.postMessage({ id, error: 'Validation engine not yet initialized' })
    return
  }

  const VALID_PARTNERS = new Set(['walmart', 'costco', 'unfi', 'kehe'])

  try {
    switch (action) {
      case 'validate': {
        if (!VALID_PARTNERS.has(data.partner)) {
          self.postMessage({ id, error: `Invalid partner: ${data.partner}` })
          break
        }

        // Receive pre-parsed rows and mapping from JS
        const rowsJson = JSON.stringify(data.rows)
        const mappingJson = JSON.stringify(data.confirmedMapping)

        const resultJson = pyodide.runPython(`
from engine.orchestrator import do_validate_rows
do_validate_rows(${JSON.stringify(rowsJson)}, ${JSON.stringify(mappingJson)}, ${JSON.stringify(data.partner)})
`)
        const result = JSON.parse(resultJson)

        if (result.error) {
          self.postMessage({ id, error: result.error })
        } else {
          self.postMessage({ id, result })
        }
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
