import { useEffect, useMemo, useState } from 'react'
import type { Reference, Row } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { flagChips } from '../../lib/flags'
import { activeFilterCount, type Filters } from '../../state/url-filters'
import { MultiSelect } from './MultiSelect'

interface Props {
  reference: Reference | undefined
  rows: Row[]
  filters: Filters
  stageLabel: (key: string) => string
  onChange: (patch: Partial<Filters>) => void
  onClear: () => void
}

export function FiltersBand({ reference, rows, filters, stageLabel, onChange, onClear }: Props) {
  const terms = useTerms()
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

  const campaignCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const row of rows) if (row.campaign) counts.set(row.campaign, (counts.get(row.campaign) ?? 0) + 1)
    return counts
  }, [rows])

  const toggleChip = (keys: string[]) => {
    const on = keys.every((key) => filters.flags.includes(key))
    const rest = filters.flags.filter((flag) => !keys.includes(flag))
    onChange({ flags: on ? rest : [...rest, ...keys] })
  }

  const count = activeFilterCount(filters)

  return (
    <section aria-label="Filters" className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <MultiSelect
          label="Type"
          options={(reference?.molecule_types ?? []).map((item) => ({
            value: item.key,
            label: item.label,
          }))}
          selected={filters.types}
          onChange={(types) => onChange({ types })}
        />
        <MultiSelect
          label="Class"
          options={(reference?.classes ?? []).map((item) => ({
            value: item.key,
            label: item.label,
          }))}
          selected={filters.classes}
          onChange={(classes) => onChange({ classes })}
        />
        <MultiSelect
          label="Campaign"
          searchable
          options={(reference?.campaigns ?? []).map((value) => ({
            value,
            label: value,
            count: campaignCounts.get(value) ?? 0,
          }))}
          selected={filters.campaigns}
          onChange={(campaigns) => onChange({ campaigns })}
        />
        <span className="mx-1 h-5 w-px bg-slate-300" aria-hidden />
        {flagChips(terms).map((chip) => {
          const on = chip.keys.every((key) => filters.flags.includes(key))
          return (
            <button
              key={chip.label}
              type="button"
              aria-pressed={on}
              className={`rounded-chip border px-2 py-1 text-xs font-semibold tracking-wide ${on ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'}`}
              onClick={() => toggleChip(chip.keys)}
            >
              {chip.label}
            </button>
          )
        })}
        <input
          type="search"
          aria-label="Search material or batch"
          placeholder="Search material or batch…"
          className="ml-auto w-64 rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      {count > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600" data-testid="active-filters">
          <span>
            {count} {count === 1 ? 'filter' : 'filters'} active
            {filters.stage ? ` · Stage: ${stageLabel(filters.stage)}` : ''}
          </span>
          <button type="button" className="text-indigo-600 underline hover:text-indigo-800" onClick={onClear}>
            Clear all
          </button>
        </div>
      )}
    </section>
  )
}
