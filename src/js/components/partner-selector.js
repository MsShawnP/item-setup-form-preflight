/**
 * partner-selector — Four partner cards for retailer/distributor selection.
 *
 * After a file is uploaded (step 2), the user picks which partner schema
 * to validate against. Selecting a partner triggers the match round trip.
 */

import { matchColumns } from '../worker-api.js'

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
      // Clone the ArrayBuffer since transferable transfer neuters it
      const originalBuffer = store.fileData.buffer
      const bufferCopy = originalBuffer.slice(0)

      const result = await matchColumns(
        bufferCopy,
        store.fileData.name,
        partnerId,
      )
      store.columnMapping = result
      store.setStep(3)
    } catch (err) {
      store.validationError = `Column matching failed: ${err.message}`
      store.selectedPartner = null
    } finally {
      this.isMatching = false
    }
  },
})
