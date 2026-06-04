import Alpine from 'alpinejs'

import { initWorker } from './worker-api.js'
import fileUpload from './components/file-upload.js'
import partnerSelector from './components/partner-selector.js'
import columnMapper from './components/column-mapper.js'
import resultsDisplay from './components/results-display.js'
import schemaDiff from './components/schema-diff.js'

Alpine.store('app', {
  // Pyodide state
  pyodideReady: false,
  loadingStatus: 'Initializing...',
  loadingError: null,

  // Workflow state
  currentStep: 1, // 1=upload, 2=partner, 3=mapping, 4=validating, 5=results
  fileData: null, // { name, size, type, buffer }
  selectedPartner: null,
  columnMapping: null, // from worker match step
  confirmedMapping: null, // user-confirmed mapping
  results: null, // validation results from worker
  viewMode: 'sku', // 'sku' or 'aggregate'
  validationError: null,

  setStep(n) {
    this.currentStep = n
  },

  reset() {
    this.currentStep = 1
    this.fileData = null
    this.selectedPartner = null
    this.columnMapping = null
    this.confirmedMapping = null
    this.results = null
    this.viewMode = 'sku'
    this.validationError = null
  },
})

// Register Alpine components
Alpine.data('fileUpload', fileUpload)
Alpine.data('partnerSelector', partnerSelector)
Alpine.data('columnMapper', columnMapper)
Alpine.data('resultsDisplay', resultsDisplay)
Alpine.data('schemaDiff', schemaDiff)

initWorker()

Alpine.start()
