import { useEffect, useState } from 'react'
import type { Reference, Row } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { useFilterPanel, type Filters } from '../../state/url-filters'
import { FilterChips, filterChips } from './FilterChips'
import { FilterPanel } from './FilterPanel'
import { TagChips } from './TagChips'

interface Props {
  reference: Reference | undefined
  rows: Row[]
  filters: Filters
  stageLabel: (key: string) => string
  onChange: (patch: Partial<Filters>) => void
  onClear: () => void
}

const button = (on: boolean) =>
  `rounded-chip border px-3 py-1.5 text-sm ${on ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'}`

/** F16-FR-01..03: the bar `[Filters] [Bookmarked] [Presets]`, the panel it toggles, and the chips shown when it is closed. */
export function FilterBar({ reference, rows, filters, stageLabel, onChange, onClear }: Props) {
  const terms = useTerms()
  const panel = useFilterPanel()
  const [search, setSearch] = useState(filters.q)
  // Follow the URL (back button, "clear all") and push typing to it after a short pause.
  const [seenQ, setSeenQ] = useState(filters.q)
  if (filters.q !== seenQ) {
    setSeenQ(filters.q)
    setSearch(filters.q)
  }
  useEffect(() => {
    if (search === filters.q) return
    const timer = setTimeout(() => onChange({ q: search }), 250)
    return () => clearTimeout(timer)
  }, [search, filters.q, onChange])

  const chips = filterChips(filters, reference, terms, stageLabel)

  return (
    <section aria-label="Filters" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-expanded={panel.open}
          aria-controls="filter-panel"
          className={button(panel.open)}
          onClick={() => panel.setOpen(!panel.open)}
        >
          {panel.open ? '▴' : '▾'} Filters
        </button>
        <input
          type="search"
          aria-label="Search material or batch"
          placeholder="Search material or batch…"
          className="ml-auto w-64 rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      {panel.open && <FilterPanel reference={reference} rows={rows} filters={filters} onChange={onChange} />}
      {!panel.open && <FilterChips chips={chips} onRemove={onChange} onClear={onClear} />}
      <TagChips flags={filters.flags} onChange={onChange} />
    </section>
  )
}
