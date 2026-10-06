import type { Reference, Row } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { useFilterPanel, type Filters } from '../../state/url-filters'
import { FilterChips, filterChips } from './FilterChips'
import { FilterPanel } from './FilterPanel'
import { PresetsMenu } from './PresetsMenu'

interface Props {
  reference: Reference | undefined
  rows: Row[]
  filters: Filters
  stageLabel: (key: string) => string
  /** The current user's bookmarked rows, whatever the filters. */
  bookmarks: string[]
  onChange: (patch: Partial<Filters>) => void
  onClear: () => void
}

const button = (on: boolean) =>
  `rounded-chip border px-3 py-1.5 text-sm ${on ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'}`

/** F16-FR-01..03: the bar `[Filters] [Bookmarked] [Presets]`, the panel it toggles, and the chips shown when it is closed. */
export function FilterBar({ reference, rows, filters, stageLabel, bookmarks, onChange, onClear }: Props) {
  const terms = useTerms()
  const panel = useFilterPanel()
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
        <button
          type="button"
          aria-pressed={filters.bookmarked}
          // Greyed until the user has a bookmark; stays usable while on, so it can always be switched off.
          disabled={bookmarks.length === 0 && !filters.bookmarked}
          title={bookmarks.length === 0 ? 'Star a batch to bookmark it' : undefined}
          className={`${button(filters.bookmarked)} disabled:cursor-not-allowed disabled:opacity-50`}
          onClick={() => onChange({ bookmarked: !filters.bookmarked })}
        >
          {filters.bookmarked ? '★' : '☆'} Bookmarked
        </button>
        <PresetsMenu filters={filters} onApply={onChange} />
      </div>
      {panel.open && <FilterPanel reference={reference} rows={rows} filters={filters} onChange={onChange} />}
      {!panel.open && <FilterChips chips={chips} onRemove={onChange} onClear={onClear} />}
    </section>
  )
}
