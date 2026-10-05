import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

/** Everything the Overview filters on. It lives in the URL query string so it can be shared and survives reload. */
export interface Filters {
  types: string[]
  classes: string[]
  campaigns: string[]
  flags: string[]
  stage: string | null
  q: string
  period: string
  from: string | null
  to: string | null
}

export const EMPTY_FILTERS: Filters = {
  types: [],
  classes: [],
  campaigns: [],
  flags: [],
  stage: null,
  q: '',
  period: 'all',
  from: null,
  to: null,
}

const LIST_KEYS = { types: 'type', classes: 'class', campaigns: 'campaign', flags: 'flag' } as const

export function parseFilters(search: URLSearchParams): Filters {
  return {
    types: search.getAll(LIST_KEYS.types),
    classes: search.getAll(LIST_KEYS.classes),
    campaigns: search.getAll(LIST_KEYS.campaigns),
    flags: search.getAll(LIST_KEYS.flags),
    stage: search.get('stage'),
    q: search.get('q') ?? '',
    period: search.get('period') ?? 'all',
    from: search.get('from'),
    to: search.get('to'),
  }
}

export function serializeFilters(filters: Filters): URLSearchParams {
  const search = new URLSearchParams()
  for (const [field, key] of Object.entries(LIST_KEYS)) {
    for (const value of filters[field as keyof typeof LIST_KEYS]) search.append(key, value)
  }
  if (filters.stage) search.set('stage', filters.stage)
  if (filters.q) search.set('q', filters.q)
  if (filters.period !== 'all') search.set('period', filters.period)
  if (filters.period === 'custom') {
    if (filters.from) search.set('from', filters.from)
    if (filters.to) search.set('to', filters.to)
  }
  return search
}

/** The query the API understands (`type[]`, `flags[]`, …). A custom period without both dates is not sent. */
export function toApiParams(filters: Filters): URLSearchParams {
  const params = new URLSearchParams()
  filters.types.forEach((value) => params.append('type[]', value))
  filters.classes.forEach((value) => params.append('class[]', value))
  filters.campaigns.forEach((value) => params.append('campaign[]', value))
  filters.flags.forEach((value) => params.append('flags[]', value))
  if (filters.stage) params.set('stage', filters.stage)
  if (filters.q) params.set('q', filters.q)
  if (filters.period === 'custom') {
    if (filters.from && filters.to) {
      params.set('period', 'custom')
      params.set('from', filters.from)
      params.set('to', filters.to)
    }
  } else if (filters.period !== 'all') {
    params.set('period', filters.period)
  }
  return params
}

/** The filters that "Clear all" resets. The period stays: it has its own selector. */
export function activeFilterCount(filters: Filters): number {
  return (
    filters.types.length +
    filters.classes.length +
    filters.campaigns.length +
    filters.flags.length +
    (filters.stage ? 1 : 0) +
    (filters.q ? 1 : 0)
  )
}

export function useUrlFilters() {
  const [search, setSearch] = useSearchParams()
  const filters = useMemo(() => parseFilters(search), [search])
  const update = useCallback(
    (patch: Partial<Filters>) => {
      setSearch((current) => serializeFilters({ ...parseFilters(current), ...patch }), { replace: true })
    },
    [setSearch],
  )
  const clearAll = useCallback(
    () => update({ types: [], classes: [], campaigns: [], flags: [], stage: null, q: '' }),
    [update],
  )
  return { filters, update, clearAll }
}
