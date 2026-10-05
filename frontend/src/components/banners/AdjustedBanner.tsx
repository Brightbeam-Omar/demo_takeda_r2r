import { useTerms } from '../../hooks/useTerms'
import { CalendarIcon } from '../common/icons'

interface Props {
  count: number
  onView: () => void
}

const TONE = 'rounded-card border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800'

/** F16-FR-06. Blue (info) with `[View details]` when there are adjusted dates, and blue with no button when there are none. Only the Insights banner turns red. */
export function AdjustedBanner({ count, onView }: Props) {
  const terms = useTerms()
  if (count === 0) {
    return (
      <div data-testid="adjusted-banner" data-state="empty" className={`${TONE} flex items-center gap-2`}>
        <CalendarIcon />
        No adjusted needs-by dates in this period
      </div>
    )
  }
  return (
    <div data-testid="adjusted-banner" data-state="active" className={`${TONE} flex items-center justify-between gap-3`}>
      <span className="flex items-center gap-2">
        <CalendarIcon />
        <span>
          <strong>{count === 1 ? '1 adjusted needs-by date' : `${count} adjusted needs-by dates`}</strong> ({terms.planner_overrides}, across all stages)
        </span>
      </span>
      <button type="button" className="rounded-chip border border-blue-300 bg-white px-3 py-1 hover:bg-blue-100" onClick={onView}>
        View details
      </button>
    </div>
  )
}
