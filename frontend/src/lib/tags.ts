import type { Terms } from '../hooks/useTerms'
import type { Filters } from '../state/url-filters'

export interface Tag {
  id: string
  label: string
  /** The API flag names; several mean "any of them" (REJECTED covers both rejection kinds, OQ-064). */
  keys: string[]
  /** Tailwind classes: the tag's own colour as an outline, and filled once selected (05 v2 section 2). */
  off: string
  on: string
}


/**
 * The tag row of the Overview, in the order of 05 v2 section 4 (6). Multi-select is OR across tags (F17-FR-08).
 * Colours: LATE red outline · REJECTED dark red · ON HOLD red · RE-EVAL blue · EXPEDITE orange outline · FULL SPEC
 * purple outline · OFFSITE TEST blue outline · RELEASE ON COA green outline · ERP BLOCKED amber · RELEASED green
 * outline · AIR GAP red outline. Written out in full so Tailwind sees every class.
 */
export const tagRow = (terms: Terms): Tag[] => [
  { id: 'late', label: 'LATE', keys: ['late'], off: 'border-red-600 text-red-600 bg-white hover:bg-red-50', on: 'border-red-600 bg-red-600 text-white' },
  { id: 'on_hold', label: 'ON HOLD', keys: ['on_hold'], off: 'border-red-700 text-red-700 bg-red-50 hover:bg-red-100', on: 'border-red-700 bg-red-700 text-white' },
  { id: 'rejected', label: 'REJECTED', keys: ['ud_rejected', 'lims_rejected'], off: 'border-red-900 text-red-900 bg-red-50 hover:bg-red-100', on: 'border-red-900 bg-red-900 text-white' },
  { id: 're_eval', label: 'RE-EVAL', keys: ['re_eval'], off: 'border-blue-600 text-blue-700 bg-blue-50 hover:bg-blue-100', on: 'border-blue-600 bg-blue-600 text-white' },
  { id: 'expedite', label: 'EXPEDITE', keys: ['expedite'], off: 'border-orange-700 text-orange-700 bg-white hover:bg-orange-50', on: 'border-orange-700 bg-orange-700 text-white' },
  { id: 'full_spec', label: 'FULL SPEC', keys: ['full_spec'], off: 'border-purple-600 text-purple-700 bg-white hover:bg-purple-50', on: 'border-purple-600 bg-purple-600 text-white' },
  { id: 'offsite', label: 'OFFSITE TEST', keys: ['offsite'], off: 'border-blue-600 text-blue-700 bg-white hover:bg-blue-50', on: 'border-blue-600 bg-blue-600 text-white' },
  { id: 'release_on_coa', label: 'RELEASE ON COA', keys: ['release_on_coa'], off: 'border-green-700 text-green-700 bg-white hover:bg-green-50', on: 'border-green-700 bg-green-700 text-white' },
  { id: 'erp_blocked', label: terms.erp_blocked_tag, keys: ['erp_blocked'], off: 'border-amber-700 text-amber-800 bg-amber-50 hover:bg-amber-100', on: 'border-amber-700 bg-amber-700 text-white' },
  { id: 'air_gap', label: 'AIR GAP', keys: ['air_gap'], off: 'border-red-600 text-red-600 bg-white hover:bg-red-50', on: 'border-red-600 bg-red-600 text-white' },
  { id: 'released', label: 'RELEASED', keys: ['released'], off: 'border-green-700 text-green-700 bg-white hover:bg-green-50', on: 'border-green-700 bg-green-700 text-white' },
]

export const tagIsOn = (tag: Tag, flags: string[]) => tag.keys.every((key) => flags.includes(key))

/** The flags after toggling one tag. */
export function toggleTag(tag: Tag, flags: string[]): string[] {
  const rest = flags.filter((flag) => !tag.keys.includes(flag))
  return tagIsOn(tag, flags) ? rest : [...rest, ...tag.keys]
}

/** The tags that are on. */
export const selectedTags = (terms: Terms, flags: string[]): Tag[] => tagRow(terms).filter((tag) => tagIsOn(tag, flags))

/** F17-FR-07: `All in-flight batches`, or a summary of the stage, tag and bookmark selection. */
export function showingText(filters: Filters, terms: Terms): string {
  const parts: string[] = []
  const stages = filters.stages.length
  if (stages > 0) parts.push(`${stages} ${stages === 1 ? 'stage' : 'stages'} selected`)
  const tags = selectedTags(terms, filters.flags).length
  if (tags > 0) parts.push(`${tags} ${tags === 1 ? 'tag' : 'tags'}`)
  if (filters.bookmarked) parts.push('bookmarked')
  return parts.length === 0 ? 'All in-flight batches' : parts.join(' · ')
}
