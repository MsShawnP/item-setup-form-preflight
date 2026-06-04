import Alpine from 'alpinejs'

import { initWorker } from './worker-api.js'

Alpine.store('app', {
  pyodideReady: false,
  loadingStatus: 'Initializing...',
  loadingError: null,
  currentStep: 1,
})

initWorker()

Alpine.start()
