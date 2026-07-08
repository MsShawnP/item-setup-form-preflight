/**
 * partner-selector — Four partner cards for retailer/distributor selection.
 *
 * After a file is uploaded (step 2), the user picks which partner schema
 * to validate against. Selecting a partner triggers column matching in JS
 * (no Pyodide needed for this step).
 */

import { parseFile } from '../file-parser.js'
import { matchColumns } from '../column-matcher.js'
import { loadSchema } from '../schema-loader.js'

const PARTNERS = [
  {
    id: 'walmart',
    name: 'Walmart',
    desc: 'Item 360 product setup',
    gtin: 'Consumer-unit UPC-12',
  },
  {
    id: 'costco',
    name: 'Costco',
    desc: 'Club item setup workbook',
    gtin: 'Case-level GTIN-14',
  },
  {
    id: 'unfi',
    name: 'UNFI',
    desc: 'Broadline distributor new item form',
    gtin: 'Case-level GTIN-14',
  },
  {
    id: 'kehe',
    name: 'KeHE',
    desc: 'Broadline distributor new item form',
    gtin: 'Case-level GTIN-14',
  },
]

export default () => ({
  partners: PARTNERS,
  isMatching: false,

  async selectPartner(partnerId) {
    const store = this.$store.app
    store.validationError = null
    store.selectedPartner = partnerId
    this.isMatching = true

    try {
      const { name, buffer } = store.fileData

      // Parse the file in JS (no Pyodide needed)
      const parsed = parseFile(buffer, name)

      // Store parsed data for the validation step
      store.parsedData = parsed

      // Load the schema and match columns in JS. Pass parsed rows so an
      // exact tie between alias columns (e.g. "upc" vs "gtin14") is broken
      // by which column's values satisfy the field's format pattern.
      const schema = loadSchema(partnerId)
      const result = matchColumns(parsed.headers, schema, partnerId, parsed.rows)

      store.columnMapping = {
        ...result,
        rowCount: parsed.rowCount,
        headers: parsed.headers,
      }
      store.setStep(3)
    } catch (err) {
      store.validationError = `Column matching failed: ${err.message}`
      store.selectedPartner = null
    } finally {
      this.isMatching = false
    }
  },
})
