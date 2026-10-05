import { expect, test } from 'vitest'
import { EMPTY_FILTERS, activeFilterCount, parseFilters, serializeFilters, toApiParams } from './url-filters'

test('F10-FR-04: filters round-trip through the URL query string', () => {
  const filters = { ...EMPTY_FILTERS, types: ['peptide', 'small_molecule'], stage: 'qc_testing', flags: ['on_hold'], q: 'B10' }
  const search = serializeFilters(filters)
  expect(search.toString()).toContain('stage=qc_testing')
  expect(parseFilters(new URLSearchParams(search.toString()))).toEqual(filters)
  expect(activeFilterCount(filters)).toBe(5)
})

test('F10-FR-04: the API query uses the bracketed names and skips an incomplete custom period', () => {
  const api = toApiParams({ ...EMPTY_FILTERS, types: ['peptide'], flags: ['air_gap'], period: 'custom', from: '2026-10-12', to: null })
  expect(api.getAll('type[]')).toEqual(['peptide'])
  expect(api.getAll('flags[]')).toEqual(['air_gap'])
  expect(api.has('period')).toBe(false)
  expect(toApiParams({ ...EMPTY_FILTERS, period: 'this_week' }).get('period')).toBe('this_week')
})
