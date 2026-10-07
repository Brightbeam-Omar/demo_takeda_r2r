import { useTerms } from '../../hooks/useTerms'
import { showingText, tagIsOn, tagRow, toggleTag } from '../../lib/tags'
import type { FilterPatch, Filters } from '../../state/url-filters'

interface Props {
  filters: Filters
  onChange: (patch: FilterPatch) => void
}

/** F17-FR-07: the `Showing:` line above the tag row. */
export function ShowingLine({ filters }: { filters: Filters }) {
  const terms = useTerms()
  return (
    <p className="text-sm text-ink-2" data-testid="showing-line">
      Showing: <span className="font-medium text-ink">{showingText(filters, terms)}</span>
    </p>
  )
}

/** F17-FR-08: `ALL LATE ON HOLD … RELEASED [Clear tags]`. ALL is on while no tag is; selected tags fill solid. */
export function TagRow({ filters, onChange }: Props) {
  const terms = useTerms()
  const tags = tagRow(terms)
  const none = filters.flags.length === 0
  const pill = 'rounded-chip border px-2.5 py-1 text-xs font-semibold tracking-wide'
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Tags" data-testid="tag-row">
      <button
        type="button"
        aria-pressed={none}
        data-testid="tag-all"
        className={`${pill} ${none ? 'border-accent bg-accent text-white' : 'border-hairline bg-white text-ink-2 hover:bg-panel'}`}
        onClick={() => onChange({ flags: [] })}
      >
        ALL
      </button>
      {tags.map((tag) => {
        const on = tagIsOn(tag, filters.flags)
        return (
          <button
            key={tag.id}
            type="button"
            aria-pressed={on}
            data-testid={`tag-${tag.id}`}
            className={`${pill} ${on ? tag.on : tag.off}`}
            onClick={() => onChange((current) => ({ flags: toggleTag(tag, current.flags) }))}
          >
            {tag.label}
          </button>
        )
      })}
      {!none && (
        <button type="button" className="text-sm text-accent underline hover:text-indigo-800" onClick={() => onChange({ flags: [] })}>
          Clear tags
        </button>
      )}
    </div>
  )
}
