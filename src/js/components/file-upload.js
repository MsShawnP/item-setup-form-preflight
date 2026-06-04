/**
 * file-upload — Drag-and-drop + file picker for product master files.
 *
 * Accepts .csv and .xlsx files. Reads the file as an ArrayBuffer and
 * stores metadata in the Alpine app store, then advances to step 2.
 */

const ALLOWED_EXTENSIONS = ['.csv', '.xlsx']
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50 MB

export default () => ({
  isDragging: false,

  handleDragOver(event) {
    event.preventDefault()
    this.isDragging = true
  },

  handleDragLeave() {
    this.isDragging = false
  },

  handleDrop(event) {
    event.preventDefault()
    this.isDragging = false
    const file = event.dataTransfer.files[0]
    if (file) this.processFile(file)
  },

  handleFileInput(event) {
    const file = event.target.files[0]
    if (file) this.processFile(file)
  },

  processFile(file) {
    const store = this.$store.app
    store.validationError = null

    // Validate extension
    const name = file.name.toLowerCase()
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))
    if (!hasValidExt) {
      store.validationError = `Unsupported file type. Expected .csv or .xlsx, got "${file.name}".`
      return
    }

    // Validate size
    if (file.size > MAX_FILE_SIZE) {
      store.validationError = `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is 50 MB.`
      return
    }

    if (file.size === 0) {
      store.validationError = 'File is empty.'
      return
    }

    // Read as ArrayBuffer
    const reader = new FileReader()
    reader.onload = () => {
      store.fileData = {
        name: file.name,
        size: file.size,
        type: file.type || (name.endsWith('.csv') ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        buffer: reader.result, // ArrayBuffer
      }
      store.setStep(2)
    }
    reader.onerror = () => {
      store.validationError = 'Failed to read file. Please try again.'
    }
    reader.readAsArrayBuffer(file)
  },
})
