/**
 * file-parser — Client-side CSV and XLSX parsing.
 *
 * Replaces the Python file_parser.py for the pre-Pyodide path.
 * Uses Papa Parse for CSV and SheetJS for Excel. Returns the same
 * shape as the Python ParseResult: { headers, rows, rowCount, format }.
 */

import Papa from 'papaparse'
import * as XLSX from 'xlsx'

export class ParseError extends Error {
  constructor(message) {
    super(message)
    this.name = 'ParseError'
  }
}

/**
 * Parse a file ArrayBuffer into headers and row dicts.
 *
 * @param {ArrayBuffer} buffer - Raw file bytes.
 * @param {string} filename - Original filename (for extension detection).
 * @returns {{ headers: string[], rows: Object[], rowCount: number, format: string }}
 */
export function parseFile(buffer, filename) {
  const lower = filename.toLowerCase().trim()
  if (lower.endsWith('.xlsx')) {
    return parseExcel(buffer)
  }
  if (lower.endsWith('.csv')) {
    return parseCsv(buffer)
  }
  throw new ParseError(
    `Unsupported file extension: '${filename}'. Expected .csv or .xlsx.`,
  )
}

/**
 * Parse CSV from an ArrayBuffer.
 */
function parseCsv(buffer) {
  const bytes = new Uint8Array(buffer)
  if (bytes.length === 0) {
    throw new ParseError('File is empty.')
  }

  const text = decodeBytes(bytes)

  const parsed = Papa.parse(text, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h) => h.trim(),
  })

  if (!parsed.meta.fields || parsed.meta.fields.length === 0) {
    throw new ParseError('CSV file contains no headers.')
  }

  const headers = parsed.meta.fields

  const rows = parsed.data.map((row) => {
    const cleaned = {}
    for (const header of headers) {
      const val = row[header]
      if (val == null || String(val).trim() === '') {
        cleaned[header] = null
      } else {
        cleaned[header] = String(val).trim()
      }
    }
    return cleaned
  })

  return { headers, rows, rowCount: rows.length, format: 'csv' }
}

/**
 * Parse Excel (.xlsx) from an ArrayBuffer.
 */
function parseExcel(buffer) {
  if (!buffer || buffer.byteLength === 0) {
    throw new ParseError('File is empty.')
  }

  let wb
  try {
    wb = XLSX.read(buffer, { type: 'array', cellDates: true })
  } catch (err) {
    throw new ParseError(`Cannot read Excel file: ${err.message}`)
  }

  const sheetName = wb.SheetNames[0]
  if (!sheetName) {
    throw new ParseError('Excel workbook has no sheets.')
  }

  const ws = wb.Sheets[sheetName]
  const jsonData = XLSX.utils.sheet_to_json(ws, { header: 1, defval: null })

  if (jsonData.length === 0) {
    throw new ParseError('Excel file contains no data.')
  }

  // First row = headers (stop at first blank cell)
  const rawHeaders = jsonData[0]
  const headers = []
  for (const val of rawHeaders) {
    if (val == null) break
    headers.push(String(val).trim())
  }

  if (headers.length === 0) {
    throw new ParseError('Excel file contains no headers in the first row.')
  }

  const rows = []
  for (let i = 1; i < jsonData.length; i++) {
    const rawRow = jsonData[i]
    const record = {}
    let hasData = false
    for (let j = 0; j < headers.length; j++) {
      const val = j < rawRow.length ? rawRow[j] : null
      const str = cellToString(val)
      record[headers[j]] = str
      if (str !== null) hasData = true
    }
    if (hasData) {
      rows.push(record)
    }
  }

  return { headers, rows, rowCount: rows.length, format: 'xlsx' }
}

/**
 * Decode bytes, handling BOM and non-UTF8.
 */
function decodeBytes(bytes) {
  // Try UTF-8 first (TextDecoder handles BOM with 'utf-8' label)
  try {
    const decoder = new TextDecoder('utf-8', { fatal: true })
    return decoder.decode(bytes)
  } catch {
    // Fall back to latin-1
    const decoder = new TextDecoder('iso-8859-1')
    return decoder.decode(bytes)
  }
}

/**
 * Convert a cell value to a string, matching Python behavior.
 */
function cellToString(value) {
  if (value == null) return null

  if (value instanceof Date) {
    return value.toISOString()
  }

  const text = String(value).trim()
  if (text === '') return null
  return text
}
