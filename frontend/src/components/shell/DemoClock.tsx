import { useClock, useReference } from '../../api/queries'
import { formatClock } from '../../lib/format'

export function DemoClock() {
  const clock = useClock()
  const reference = useReference()
  if (!clock.data || !reference.data) return <span className="text-sm text-slate-400">…</span>
  return (
    <span data-testid="demo-clock" title="Demo clock" className="text-sm font-medium text-slate-600 tabular-nums">
      {formatClock(clock.data.now_utc, reference.data.site_timezone)}
    </span>
  )
}
