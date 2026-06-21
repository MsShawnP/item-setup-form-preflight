/**
 * column-matcher — Fuzzy column matching engine (JS port).
 *
 * Maps uploaded file headers to schema fields using a layered approach:
 * exact match after normalization, alias substring containment, then
 * fuzzy matching via SequenceMatcher-equivalent ratio. Port of the
 * Python column_matcher.py — same algorithm, same thresholds.
 */

// ---------------------------------------------------------------------------
// Partner-specific alias maps
// ---------------------------------------------------------------------------

const WALMART_ALIASES = {
  upc: [
    'upc', 'upc-a', 'upc_a', 'upc a', 'upc number', 'upc code',
    'gtin', 'gtin12', 'gtin-12', 'gtin 12', 'barcode',
  ],
  case_gross_weight_lb: [
    'gross weight', 'gross wt', 'case weight', 'weight',
    'case gross weight', 'case gross weight lb',
  ],
  case_length_in: [
    'length', 'case length', 'item length', 'l in', 'case length in',
  ],
  case_width_in: [
    'width', 'case width', 'item width', 'w in', 'item width in',
    'case width in',
  ],
  case_height_in: [
    'height', 'case height', 'item height', 'h in', 'case height in',
  ],
  case_pack_qty: [
    'case pack', 'pack qty', 'pack quantity', 'case count',
    'qty per case', 'cs pk', 'case pack qty',
  ],
  product_name: [
    'product name', 'item name', 'product', 'name',
    'description', 'item description',
  ],
  brand: ['brand', 'brand name', 'manufacturer'],
  category: ['category', 'department', 'class', 'segment'],
  country_of_origin: ['country of origin', 'coo', 'country', 'origin'],
  serving_size: ['serving size', 'srv size', 'portion'],
  calories: ['calories', 'kcal', 'cal'],
  storage_type: ['storage type', 'storage', 'temp class', 'temp zone'],
  product_description: [
    'product description', 'long description', 'item desc',
    'item description',
  ],
  total_fat_g: ['total fat', 'total fat g', 'fat g', 'fat'],
  sodium_mg: ['sodium', 'sodium mg', 'na mg', 'salt'],
}

const COSTCO_ALIASES = {
  upc: [
    'upc', 'gtin', 'gtin14', 'gtin-14', 'gtin 14', 'itf-14',
    'itf14', 'itf 14', 'case gtin', 'case barcode', 'barcode',
  ],
  case_pack_qty: [
    'club pack qty', 'club pack quantity', 'pack qty',
    'pack quantity', 'case count', 'case pack qty',
  ],
  inner_pack_count: [
    'inner pack count', 'inner pack', 'inner pack qty',
    'inner count', 'inners per case',
  ],
  club_pack_length_in: [
    'club pack length', 'club pack length in', 'club length', 'club pack l',
  ],
  club_pack_width_in: [
    'club pack width', 'club pack width in', 'club width', 'club pack w',
  ],
  club_pack_height_in: [
    'club pack height', 'club pack height in', 'club height', 'club pack h',
  ],
  shelf_life_days: [
    'shelf life', 'shelf life days', 'best by days', 'days of shelf life',
  ],
  club_membership_tier: [
    'club membership tier', 'membership tier', 'member tier',
    'membership level',
  ],
  executive_member_price: [
    'executive member price', 'executive price', 'exec member price',
  ],
  executive_discount_pct: [
    'executive discount pct', 'executive discount',
    'exec discount', 'executive discount percent',
  ],
}

const UNFI_ALIASES = {
  upc: [
    'upc', 'gtin', 'gtin14', 'gtin-14', 'gtin 14', 'itf-14',
    'itf14', 'itf 14', 'case gtin', 'case barcode', 'barcode',
  ],
  wholesale_price: [
    'wholesale price', 'wholesale', 'whs price', 'whsl', 'wholesale cost',
  ],
  list_price: [
    'list price', 'list', 'srp', 'retail price', 'suggested retail price',
  ],
  map_price: [
    'map price', 'map', 'minimum advertised price', 'min advertised price',
  ],
  ti: ['ti', 'cases per layer', 'cases per tier', 'case per layer', 'tier count'],
  hi: ['hi', 'layers per pallet', 'layers', 'pallet layers', 'layer count', 'high'],
  pallet_weight_lb: [
    'pallet weight', 'pallet weight lb', 'pallet wt',
    'plt weight', 'full pallet weight',
  ],
  shelf_life_days: [
    'shelf life', 'shelf life days', 'best by days', 'days of shelf life',
  ],
  has_promo_deal: ['has promo deal', 'promo deal', 'has promotion', 'deal flag'],
  promo_start_date: [
    'promo start date', 'promo start', 'deal start', 'promotion start',
  ],
  promo_end_date: [
    'promo end date', 'promo end', 'deal end', 'promotion end',
  ],
  promo_price: [
    'promo price', 'deal price', 'promotional price', 'promotion price',
  ],
}

const KEHE_ALIASES = {
  upc: [
    'upc', 'gtin', 'gtin14', 'gtin-14', 'gtin 14', 'itf-14',
    'itf14', 'itf 14', 'case gtin', 'case barcode', 'barcode',
  ],
  wholesale_price: [
    'wholesale price', 'wholesale', 'whs price', 'whsl', 'wholesale cost',
  ],
  list_price: [
    'list price', 'list', 'srp', 'retail price', 'suggested retail price',
  ],
  cases_per_layer: [
    'cases per layer', 'ti', 'cases per tier', 'case per layer', 'tier count',
  ],
  layers_per_pallet: [
    'layers per pallet', 'hi', 'layers', 'pallet layers', 'layer count', 'high',
  ],
  pallet_weight_lb: [
    'pallet weight', 'pallet weight lb', 'pallet wt',
    'plt weight', 'full pallet weight',
  ],
  shelf_life_days: [
    'shelf life', 'shelf life days', 'best by days', 'days of shelf life',
  ],
  has_promo_deal: ['has promo deal', 'promo deal', 'has promotion', 'deal flag'],
  promo_start_date: [
    'promo start date', 'promo start', 'deal start', 'promotion start',
  ],
  promo_end_date: [
    'promo end date', 'promo end', 'deal end', 'promotion end',
  ],
  promo_price: [
    'promo price', 'deal price', 'promotional price', 'promotion price',
  ],
}

const PARTNER_ALIAS_MAPS = {
  walmart: WALMART_ALIASES,
  costco: COSTCO_ALIASES,
  unfi: UNFI_ALIASES,
  kehe: KEHE_ALIASES,
}

// Build merged global alias map
const ALIAS_MAP = {}
for (const partnerMap of [WALMART_ALIASES, COSTCO_ALIASES, UNFI_ALIASES, KEHE_ALIASES]) {
  for (const [field, aliases] of Object.entries(partnerMap)) {
    if (!ALIAS_MAP[field]) ALIAS_MAP[field] = []
    const seen = new Set(ALIAS_MAP[field])
    for (const a of aliases) {
      if (!seen.has(a)) {
        ALIAS_MAP[field].push(a)
        seen.add(a)
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Normalization
// ---------------------------------------------------------------------------

function normalize(text) {
  const lowered = text.toLowerCase().trim()
  const cleaned = lowered.replace(/[^a-z0-9 ]/g, ' ')
  return cleaned.replace(/\s+/g, ' ').trim()
}

// ---------------------------------------------------------------------------
// Fuzzy matching (SequenceMatcher-equivalent ratio)
// ---------------------------------------------------------------------------

/**
 * Compute string similarity ratio matching Python's difflib.SequenceMatcher.
 * Finds matching character blocks and returns 2*M/T where M is total
 * matching characters and T is total characters in both strings.
 */
function sequenceMatchRatio(a, b) {
  if (a.length === 0 && b.length === 0) return 1.0
  if (a.length === 0 || b.length === 0) return 0.0

  const matches = findMatchingBlocks(a, b)
  let totalMatching = 0
  for (const [, , size] of matches) {
    totalMatching += size
  }
  return (2.0 * totalMatching) / (a.length + b.length)
}

/**
 * Find matching blocks between two strings.
 * Returns array of [aIdx, bIdx, size] triples.
 */
function findMatchingBlocks(a, b) {
  const blocks = []
  findBlocks(a, b, 0, a.length, 0, b.length, blocks)
  blocks.sort((x, y) => x[0] - y[0] || x[1] - y[1])
  return blocks
}

function findBlocks(a, b, aLo, aHi, bLo, bHi, blocks) {
  // Find longest common substring in a[aLo..aHi) and b[bLo..bHi)
  let bestI = aLo
  let bestJ = bLo
  let bestSize = 0

  // Use a simple O(n*m) approach — fine for short column name strings
  for (let i = aLo; i < aHi; i++) {
    for (let j = bLo; j < bHi; j++) {
      let k = 0
      while (i + k < aHi && j + k < bHi && a[i + k] === b[j + k]) {
        k++
      }
      if (k > bestSize) {
        bestI = i
        bestJ = j
        bestSize = k
      }
    }
  }

  if (bestSize > 0) {
    blocks.push([bestI, bestJ, bestSize])
    if (aLo < bestI && bLo < bestJ) {
      findBlocks(a, b, aLo, bestI, bLo, bestJ, blocks)
    }
    if (bestI + bestSize < aHi && bestJ + bestSize < bHi) {
      findBlocks(a, b, bestI + bestSize, aHi, bestJ + bestSize, bHi, blocks)
    }
  }
}

// ---------------------------------------------------------------------------
// Matching engine
// ---------------------------------------------------------------------------

const EXACT_CONFIDENCE = 1.0
const CONTAINMENT_CONFIDENCE_HIGH = 0.9
const CONTAINMENT_CONFIDENCE_LOW = 0.7
const FUZZY_THRESHOLD = 0.6

function getEffectiveAliases(partner, fieldName) {
  const partnerMap = PARTNER_ALIAS_MAPS[partner] || {}
  if (fieldName in partnerMap) {
    return partnerMap[fieldName]
  }
  return ALIAS_MAP[fieldName] || [fieldName]
}

/**
 * Match uploaded file headers to schema fields.
 *
 * @param {string[]} headers - Column headers from the uploaded file.
 * @param {Object} schema - Parsed schema config with required_fields array.
 * @param {string} partner - Partner key (walmart|costco|unfi|kehe).
 * @returns {{ mapping: Object[], unmatchedHeaders: string[], unmatchedFields: string[], rowCount: number, headers: string[] }}
 */
export function matchColumns(headers, schema, partner) {
  const schemaFields = schema.required_fields.map((f) => f.name)
  const normHeaders = headers.map((h) => normalize(h))
  const claimed = new Set()
  const matches = []

  for (const fieldName of schemaFields) {
    const match = matchSingleField(fieldName, headers, normHeaders, claimed, partner)
    if (match.uploadedHeader !== null) {
      const idx = headers.findIndex(
        (h, i) => h === match.uploadedHeader && !claimed.has(i),
      )
      if (idx !== -1) claimed.add(idx)
    }
    matches.push(match)
  }

  const unmatchedHeaders = headers.filter((_, i) => !claimed.has(i))
  const unmatchedFields = matches
    .filter((m) => m.status === 'unmatched')
    .map((m) => m.schemaField)

  return {
    mapping: matches,
    unmatchedHeaders,
    unmatchedFields,
  }
}

function matchSingleField(fieldName, headers, normHeaders, claimed, partner) {
  const normField = normalize(fieldName)
  const aliases = partner
    ? getEffectiveAliases(partner, fieldName)
    : ALIAS_MAP[fieldName] || [fieldName]

  const allAliases = new Set(aliases)
  allAliases.add(fieldName)
  allAliases.add(normField)
  const normAliases = new Set()
  for (const a of allAliases) {
    normAliases.add(normalize(a))
  }

  // Layer 1: Exact match
  for (let idx = 0; idx < normHeaders.length; idx++) {
    if (claimed.has(idx)) continue
    if (normAliases.has(normHeaders[idx])) {
      return {
        schemaField: fieldName,
        uploadedHeader: headers[idx],
        confidence: EXACT_CONFIDENCE,
        status: 'matched',
        candidates: [],
      }
    }
  }

  // Layer 2: Containment
  let bestContainment = null
  for (let idx = 0; idx < normHeaders.length; idx++) {
    if (claimed.has(idx)) continue
    const normH = normHeaders[idx]
    for (const alias of normAliases) {
      if (!alias || !normH) continue
      if (alias.includes(normH) || normH.includes(alias)) {
        const overlap =
          Math.min(alias.length, normH.length) /
          Math.max(alias.length, normH.length)
        const span = CONTAINMENT_CONFIDENCE_HIGH - CONTAINMENT_CONFIDENCE_LOW
        const conf = CONTAINMENT_CONFIDENCE_LOW + overlap * span
        if (!bestContainment || conf > bestContainment.conf) {
          bestContainment = { idx, conf }
        }
      }
    }
  }

  if (bestContainment) {
    return {
      schemaField: fieldName,
      uploadedHeader: headers[bestContainment.idx],
      confidence: Math.round(bestContainment.conf * 1000) / 1000,
      status: 'matched',
      candidates: [],
    }
  }

  // Layer 3: Fuzzy matching
  const candidates = []
  for (let idx = 0; idx < normHeaders.length; idx++) {
    if (claimed.has(idx)) continue
    let bestRatio = 0
    for (const alias of normAliases) {
      const ratio = sequenceMatchRatio(normHeaders[idx], alias)
      if (ratio > bestRatio) bestRatio = ratio
    }
    if (bestRatio >= FUZZY_THRESHOLD) {
      candidates.push({ idx, ratio: bestRatio })
    }
  }

  if (candidates.length === 0) {
    return {
      schemaField: fieldName,
      uploadedHeader: null,
      confidence: 0,
      status: 'unmatched',
      candidates: [],
    }
  }

  candidates.sort((a, b) => b.ratio - a.ratio)

  if (candidates.length === 1 || candidates[0].ratio - candidates[1].ratio > 0.05) {
    const best = candidates[0]
    return {
      schemaField: fieldName,
      uploadedHeader: headers[best.idx],
      confidence: Math.round(best.ratio * 1000) / 1000,
      status: 'matched',
      candidates: [],
    }
  }

  return {
    schemaField: fieldName,
    uploadedHeader: null,
    confidence: Math.round(candidates[0].ratio * 1000) / 1000,
    status: 'ambiguous',
    candidates: candidates.map((c) => headers[c.idx]),
  }
}
