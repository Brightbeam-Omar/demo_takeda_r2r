import { useTerms } from '../../hooks/useTerms'

interface Props {
  count: number
  onView: () => void
}

/** F16-FR-06. Amber with `[View details]` when there are adjusted dates; the blue empty state when there are none. */
export function AdjustedBanner({ count, onView }: Props) {
  const terms = useTerms()
  if (count === 0) {
    return (
      <div data-testid="adjusted-banner" data-state="empty" className="rounded-card border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
        📅 No adjusted needs-by dates in this period
      </div>
    )
  }
  return (
    <div data-testid="adjusted-banner" data-state="active" className="flex items-center justify-between gap-3 rounded-card border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <span>
        📅 <strong>{count === 1 ? '1 adjusted needs-by date' : `${count} adjusted needs-by dates`}</strong> ({terms.planner_overrides}, across all stages)
      </span>
      <button type="button" className="rounded-chip border border-amber-300 bg-white px-3 py-1 hover:bg-amber-100" onClick={onView}>
        View details
      </button>
    </div>
  )
}
