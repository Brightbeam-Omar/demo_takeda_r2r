import { useTerms } from '../../hooks/useTerms'

interface Props {
  count: number
  onView: () => void
}

/** F16-FR-08. Red with `[View all N →]` when there are air-gap batches; the blue empty state when there are none. */
export function InsightsBanner({ count, onView }: Props) {
  const terms = useTerms()
  if (count === 0) {
    return (
      <div data-testid="insights-banner" data-state="empty" className="rounded-card border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
        ⓘ No {terms.insights_banner} in this period
      </div>
    )
  }
  return (
    <div data-testid="insights-banner" data-state="active" className="flex items-center justify-between gap-3 rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <span>
        ⓘ <strong>{terms.insights_banner}</strong> ({count} {count === 1 ? 'batch' : 'batches'})
      </span>
      <button type="button" className="rounded-chip border border-red-300 bg-white px-3 py-1 hover:bg-red-100" onClick={onView}>
        View all {count} →
      </button>
    </div>
  )
}
