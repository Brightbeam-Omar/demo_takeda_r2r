import type { Reference } from '../../api/queries'
import type { Terms } from '../../hooks/useTerms'
import { selectedTags } from '../../lib/tags'
import type { Filters } from '../../state/url-filters'

export interface Chip {
  id: string
  text: string
  remove: Partial<Filters>
}

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? '' : noun.endsWith('s') ? 'es' : 's'}`

/** One chip per active filter: a single value reads `Type: Small Molecule`, several read `Class: 2 classes` (F16-FR-03). */
export function filterChips(
  filters: Filters,
  reference: Reference | undefined,
  terms: Terms,
  stageLabel: (key: string) => string,
): Chip[] {
  const labelled = (items: Record<string, string>[] | undefined, key: string) =>
    items?.find((item) => item['key'] === key)?.['label'] ?? (key === 'unknown' ? 'Unknown' : key)
  const chips: Chip[] = []
  const list = (id: keyof Pick<Filters, 'types' | 'classes' | 'campaigns'>, name: string, noun: string, name1: (key: string) => string) => {
    const values = filters[id]
    if (values.length === 0) return
    chips.push({
      id,
      text: `${name}: ${values.length === 1 ? name1(values[0]!) : plural(values.length, noun)}`,
      remove: { [id]: [] },
    })
  }
  list('types', 'Type', 'type', (key) => labelled(reference?.molecule_types, key))
  list('classes', 'Class', 'class', (key) => labelled(reference?.classes, key))
  list('campaigns', 'Campaign', 'campaign', (key) => key)
  if (filters.stages.length > 0) {
    const text = filters.stages.length === 1 ? stageLabel(filters.stages[0]!) : plural(filters.stages.length, 'stage')
    chips.push({ id: 'stage', text: `Stage: ${text}`, remove: { stages: [] } })
  }
  for (const tag of selectedTags(terms, filters.flags)) {
    chips.push({ id: `tag-${tag.id}`, text: `Tag: ${tag.label}`, remove: { flags: filters.flags.filter((flag) => !tag.keys.includes(flag)) } })
  }
  if (filters.bookmarked) chips.push({ id: 'bookmarked', text: 'Bookmarked', remove: { bookmarked: false } })
  if (filters.q) chips.push({ id: 'q', text: `Search: “${filters.q}”`, remove: { q: '' } })
  return chips
}

interface Props {
  chips: Chip[]
  onRemove: (patch: Partial<Filters>) => void
  onClear: () => void
}

export function FilterChips({ chips, onRemove, onClear }: Props) {
  if (chips.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="filter-chips">
      {chips.map((chip) => (
        <span key={chip.id} className="inline-flex items-center gap-1 rounded-pill border border-indigo-200 bg-indigo-50 py-0.5 pr-1 pl-3 text-sm text-indigo-700">
          {chip.text}
          <button
            type="button"
            aria-label={`Remove ${chip.text}`}
            className="rounded-pill px-1.5 text-indigo-500 hover:bg-indigo-100 hover:text-indigo-800"
            onClick={() => onRemove(chip.remove)}
          >
            ×
          </button>
        </span>
      ))}
      <button type="button" className="text-sm text-indigo-600 underline hover:text-indigo-800" onClick={onClear}>
        Clear all
      </button>
    </div>
  )
}
