/**
 * schema-loader — Load partner schemas from YAML into JS objects.
 *
 * Uses js-yaml to parse the YAML strings imported via Vite's ?raw.
 * Returns plain objects matching the SchemaConfig shape from the
 * Python models.py, without Pydantic validation (the YAML files
 * are static and already validated in the Python test suite).
 */

import { load as yamlLoad } from 'js-yaml'

import walmartYaml from '../schemas/walmart.yaml?raw'
import costcoYaml from '../schemas/costco.yaml?raw'
import unfiYaml from '../schemas/unfi.yaml?raw'
import keheYaml from '../schemas/kehe.yaml?raw'

const SCHEMA_SOURCES = {
  walmart: walmartYaml,
  costco: costcoYaml,
  unfi: unfiYaml,
  kehe: keheYaml,
}

const schemaCache = {}

/**
 * Load a partner schema by key.
 *
 * @param {string} partner - Partner key (walmart|costco|unfi|kehe).
 * @returns {Object} Parsed schema config.
 */
export function loadSchema(partner) {
  if (schemaCache[partner]) return schemaCache[partner]

  const source = SCHEMA_SOURCES[partner]
  if (!source) {
    throw new Error(`Unknown partner: ${partner}`)
  }

  const data = yamlLoad(source)
  schemaCache[partner] = data
  return data
}

/**
 * Load all four partner schemas.
 *
 * @returns {Object} Map of partner key to schema config.
 */
export function loadAllSchemas() {
  const schemas = {}
  for (const partner of Object.keys(SCHEMA_SOURCES)) {
    schemas[partner] = loadSchema(partner)
  }
  return schemas
}

export const VALID_PARTNERS = new Set(Object.keys(SCHEMA_SOURCES))
