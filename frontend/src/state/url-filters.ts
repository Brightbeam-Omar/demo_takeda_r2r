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
      setSearch(
        (current) => {
          const next = serializeFilters({ ...parseFilters(current), ...patch })
          const row = current.get('row') // the open drawer is not a filter, but it must survive one
          if (row) next.set('row', row)
          return next
        },
        { replace: true },
      )
    },
    [setSearch],
  )
  const clearAll = useCallback(
    () => update({ types: [], classes: [], campaigns: [], flags: [], stage: null, q: '' }),
    [update],
  )
  return { filters, update, clearAll }
}

/** The batch whose drawer is open (`?row=<row_key>`, F11-FR-07). Closing removes only this parameter. */
export function useDrawerRow() {
  const [search, setSearch] = useSearchParams()
  const row = search.get('row')
  const open = useCallback(
    (rowKey: string | null) =>
      setSearch(
        (current) => {
          const next = new URLSearchParams(current)
          if (rowKey) next.set('row', rowKey)
          else next.delete('row')
          return next
        },
        { replace: true },
      ),
    [setSearch],
  )
  return { row, open }
}
