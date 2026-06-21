import Alpine from 'alpinejs'

import { initWorker } from './worker-api.js'
import fileUpload from './components/file-upload.js'
import partnerSelector from './components/partner-selector.js'
import columnMapper from './components/column-mapper.js'
import resultsDisplay from './components/results-display.js'
import schemaDiff from './components/schema-diff.js'

Alpine.store('app', {
  // Validation engine state (Pyodide loads in background)
  engineReady: false,
  engineStatus: 'Loading validation engine...',
  engineError: null,

  // Workflow state
  currentStep: 1,
  fileData: null,
  parsedData: null,
  selectedPartner: null,
  columnMapping: null,
  confirmedMapping: null,
  results: null,
  viewMode: 'sku',
  validationError: null,

  setStep(n) {
    this.currentStep = n
  },

  reset() {
    this.currentStep = 1
    this.fileData = null
    this.parsedData = null
    this.selectedPartner = null
    this.columnMapping = null
    this.confirmedMapping = null
    this.results = null
    this.viewMode = 'sku'
    this.validationError = null
  },
})

Alpine.data('fileUpload', fileUpload)
Alpine.data('partnerSelector', partnerSelector)
Alpine.data('columnMapper', columnMapper)
Alpine.data('resultsDisplay', resultsDisplay)
Alpine.data('schemaDiff', schemaDiff)

window.Alpine = Alpine

// Start Pyodide worker in background — UI is usable immediately
initWorker()

Alpine.start()
