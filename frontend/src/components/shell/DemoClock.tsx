import { useClock, useReference } from '../../api/queries'
import { formatTopBarClock } from '../../lib/format'

export function DemoClock() {
  const clock = useClock()
  const reference = useReference()
  if (!clock.data || !reference.data) return <span className="text-sm text-ink-3">…</span>
  return (
    <span data-testid="demo-clock" title="Demo clock" className="text-sm font-medium text-ink-2 tabular-nums">
      {formatTopBarClock(clock.data.now_utc, reference.data.site_timezone)}
    </span>
  )
}
