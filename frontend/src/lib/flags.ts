import type { Terms } from '../hooks/useTerms'

export interface FlagChip {
  label: string
  keys: string[]
  tone: 'neutral' | 'amber' | 'red'
}

/** Tag chips in the order of 05. `keys` are the API flag names; REJECTED covers both rejection kinds (OQ-064). The blocked tag is profile vocabulary (F15-FR-05). */
export const flagChips = (terms: Terms): FlagChip[] => [
  { label: 'HOLD', keys: ['on_hold'], tone: 'amber' },
  { label: 'RE-EVAL', keys: ['re_eval'], tone: 'neutral' },
  { label: 'EXPEDITE', keys: ['expedite'], tone: 'neutral' },
  { label: 'FULL SPEC', keys: ['full_spec'], tone: 'neutral' },
  { label: 'OFFSITE', keys: ['offsite'], tone: 'neutral' },
  { label: terms.erp_blocked_tag, keys: ['erp_blocked'], tone: 'red' },
  { label: 'REJECTED', keys: ['ud_rejected', 'lims_rejected'], tone: 'red' },
  { label: 'AIR GAP', keys: ['air_gap'], tone: 'red' },
]
