const PYODIDE_CDN = 'https://cdn.jsdelivr.net/pyodide/v0.29.4/full/'

// Import Python source files as raw strings (Vite ?raw imports)
import engineInit from '../engine/__init__.py?raw'
import modelsCode from '../engine/models.py?raw'
import validatorsCode from '../engine/validators.py?raw'
import schemaLoaderCode from '../engine/schema_loader.py?raw'
import columnMatcherCode from '../engine/column_matcher.py?raw'
import fileParserCode from '../engine/file_parser.py?raw'
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

/**
 * Rewrite Python import paths for the Pyodide environment.
 *
 * Locally the engine uses `from src.engine.X import Y` but inside
 * Pyodide the package lives at /home/pyodide/engine/ so the imports
 * need to be `from engine.X import Y`.
 */
function rewriteImports(source) {
  return source.replace(/from src\.engine\./g, 'from engine.')
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
    await micropip.install('pyyaml')
    await micropip.install('openpyxl')

    postStatus('Loading engine...')

    // Write Python engine to Pyodide virtual filesystem
    pyodide.FS.mkdirTree('/home/pyodide/engine/gtin')

    pyodide.FS.writeFile('/home/pyodide/engine/__init__.py', rewriteImports(engineInit))
    pyodide.FS.writeFile('/home/pyodide/engine/models.py', rewriteImports(modelsCode))
    pyodide.FS.writeFile('/home/pyodide/engine/validators.py', rewriteImports(validatorsCode))
    pyodide.FS.writeFile('/home/pyodide/engine/schema_loader.py', rewriteImports(schemaLoaderCode))
    pyodide.FS.writeFile('/home/pyodide/engine/column_matcher.py', rewriteImports(columnMatcherCode))
    pyodide.FS.writeFile('/home/pyodide/engine/file_parser.py', rewriteImports(fileParserCode))
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
    pyodide.runPython('from engine.orchestrator import do_match, do_validate')

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

      case 'match': {
        // data.file is an ArrayBuffer, data.filename is a string,
        // data.partner is a string (walmart|costco|unfi|kehe)
        const fileBytes = new Uint8Array(data.file)
        const tempPath = `/home/pyodide/upload/${data.filename}`

        // Write the uploaded file to Pyodide FS
        pyodide.FS.mkdirTree('/home/pyodide/upload')
        pyodide.FS.writeFile(tempPath, fileBytes)

        // Run the Python orchestrator
        const resultJson = pyodide.runPython(`
from engine.orchestrator import do_match
do_match(${JSON.stringify(tempPath)}, ${JSON.stringify(data.filename)}, ${JSON.stringify(data.partner)})
`)
        const result = JSON.parse(resultJson)

        // Clean up the uploaded file
        try {
          pyodide.FS.unlink(tempPath)
        } catch (_) {
          // Non-critical cleanup
        }

        self.postMessage({ id, result })
        break
      }

      case 'validate': {
        // data.confirmedMapping is an object: { schemaField: uploadedHeader, ... }
        // data.partner is a string
        const mappingJson = JSON.stringify(data.confirmedMapping)

        const resultJson = pyodide.runPython(`
from engine.orchestrator import do_validate
do_validate(${JSON.stringify(mappingJson)}, ${JSON.stringify(data.partner)})
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
