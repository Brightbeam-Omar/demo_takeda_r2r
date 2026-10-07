import { useCallback, useEffect, useMemo } from 'react'
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
const KEPT_PARAMS = ['row', 'win', 'drawer', 'filters'] as const

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
  // `q` is not sent: the table's search runs in the browser over the displayed text (F18-FR-05).
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

/** A change to the filters: the new values, or a function of the latest filters (for toggles, which must not use stale props). */
export type FilterPatch = Partial<Filters> | ((current: Filters) => Partial<Filters>)

/** Adds the value to the list, or removes it when it is already there. */
export const toggled = (list: string[], value: string) => (list.includes(value) ? list.filter((item) => item !== value) : [...list, value])

/** The params the last click produced, until the router has rendered them (null once it has caught up). */
let pending: { params: URLSearchParams; at: number } | null = null
/** Safety net: a click that never reached the router must not pin the params for ever. */
const PENDING_MS = 1000

/**
 * Rapid clicks can arrive before React re-renders, and react-router hands every updater the params of the last
 * render. Every URL change that builds on the current params (a pill, the Filters toggle) goes through this hook,
 * which remembers what the previous click produced, so no click is lost.
 */
function useLatestSearch() {
  const [search, setSearch] = useSearchParams()
  useEffect(() => {
    if (pending && pending.params.toString() === search.toString()) pending = null
  }, [search])
  const read = useCallback(
    () => (pending && performance.now() - pending.at < PENDING_MS ? pending.params : search),
    [search],
  )
  const commit = useCallback(
    (next: URLSearchParams) => {
      pending = { params: next, at: performance.now() }
      setSearch(next, { replace: true })
    },
    [setSearch],
  )
  return { search, read, commit }
}

export function useUrlFilters() {
  const { search, read, commit } = useLatestSearch()
  const filters = useMemo(() => parseFilters(search), [search])
  const update = useCallback(
    (patch: FilterPatch) => {
      const current = read()
      const base = parseFilters(current)
      const next = serializeFilters({ ...base, ...(typeof patch === 'function' ? patch(base) : patch) })
      // The open drawer and the panel state are not filters, but they must survive one.
      for (const key of KEPT_PARAMS) {
        const value = current.get(key)
        if (value) next.set(key, value)
      }
      commit(next)
    },
    [read, commit],
  )
  const clearAll = useCallback(
    () => update({ types: [], classes: [], campaigns: [], flags: [], stages: [], bookmarked: false, q: '' }),
    [update],
  )
  return { filters, update, clearAll }
}

/** The filter panel is open or closed (`?filters=open|closed`, F16-FR-01). Closed unless the URL says open. */
export function useFilterPanel() {
  const { search, read, commit } = useLatestSearch()
  const open = search.get('filters') === 'open'
  const setOpen = useCallback(
    (next: boolean) => {
      const params = new URLSearchParams(read())
      params.set('filters', next ? 'open' : 'closed')
      commit(params)
    },
    [read, commit],
  )
  return { open, setOpen }
}
