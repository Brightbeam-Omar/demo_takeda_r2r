/** Tag chips in the order of 05. `keys` are the API flag names; REJECTED covers both rejection kinds (OQ-064). */
export const FLAG_CHIPS: { label: string; keys: string[]; tone: 'neutral' | 'amber' | 'red' }[] = [
  { label: 'HOLD', keys: ['on_hold'], tone: 'amber' },
  { label: 'RE-EVAL', keys: ['re_eval'], tone: 'neutral' },
  { label: 'EXPEDITE', keys: ['expedite'], tone: 'neutral' },
  { label: 'FULL SPEC', keys: ['full_spec'], tone: 'neutral' },
  { label: 'OFFSITE', keys: ['offsite'], tone: 'neutral' },
  { label: 'ERP BLOCKED', keys: ['erp_blocked'], tone: 'red' },
  { label: 'REJECTED', keys: ['ud_rejected', 'lims_rejected'], tone: 'red' },
  { label: 'AIR GAP', keys: ['air_gap'], tone: 'red' },
]
