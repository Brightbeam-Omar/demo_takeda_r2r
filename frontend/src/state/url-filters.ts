import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

/** Everything the Overview filters on. It lives in the URL query string so it can be shared and survives reload. */
export interface Filters {
  types: string[]
  classes: string[]
  campaigns: string[]
  flags: string[]
  stages: string[]
  bookmarked: boolean
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
  stages: [],
  bookmarked: false,
  q: '',
  period: 'all',
  from: null,
  to: null,
}

const LIST_KEYS = { types: 'type', classes: 'class', campaigns: 'campaign', flags: 'flag' } as const

/** URL parameters that are view state, not filters: `update` carries them over. */
const KEPT_PARAMS = ['row', 'filters'] as const

export function parseFilters(search: URLSearchParams): Filters {
  return {
    types: search.getAll(LIST_KEYS.types),
    classes: search.getAll(LIST_KEYS.classes),
    campaigns: search.getAll(LIST_KEYS.campaigns),
    flags: search.getAll(LIST_KEYS.flags),
    stages: search.getAll('stage'),
    bookmarked: search.get('bookmarked') === '1',
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
  for (const stage of filters.stages) search.append('stage', stage)
  if (filters.bookmarked) search.set('bookmarked', '1')
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
  filters.stages.forEach((value) => params.append('stage', value))
  if (filters.bookmarked) params.set('bookmarked', 'true')
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
    filters.stages.length +
    (filters.bookmarked ? 1 : 0) +
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
          // The open drawer and the panel state are not filters, but they must survive one.
          for (const key of KEPT_PARAMS) {
            const value = current.get(key)
            if (value) next.set(key, value)
          }
          return next
        },
        { replace: true },
      )
    },
    [setSearch],
  )
  const clearAll = useCallback(
    () => update({ types: [], classes: [], campaigns: [], flags: [], stages: [], bookmarked: false, q: '' }),
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

/** The filter panel is open or closed (`?filters=open|closed`, F16-FR-01). Closed unless the URL says open. */
export function useFilterPanel() {
  const [search, setSearch] = useSearchParams()
  const open = search.get('filters') === 'open'
  const setOpen = useCallback(
    (next: boolean) =>
      setSearch(
        (current) => {
          const params = new URLSearchParams(current)
          params.set('filters', next ? 'open' : 'closed')
          return params
        },
        { replace: true },
      ),
    [setSearch],
  )
  return { open, setOpen }
}
