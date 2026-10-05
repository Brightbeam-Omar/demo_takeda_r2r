import { useClock, useSyncStatus } from '../../api/queries'
import { formatFeedAge, freshnessTone, minutesBetween, type FreshnessTone } from '../../lib/format'

const TONES: Record<FreshnessTone | 'none', string> = {
  green: 'bg-emerald-50 text-emerald-700',
  amber: 'bg-amber-50 text-amber-700',
  red: 'bg-red-50 text-red-700',
  none: 'bg-panel text-ink-2',
}

/** Demo-clock now minus the last successful pipeline run (OQ-065, OQ-080). Both sources poll every 10 s. */
export function FreshnessPill() {
  const clock = useClock()
  const sync = useSyncStatus()
  const lastRun = sync.data?.pipeline_status?.last_success_at
  if (!clock.data || !lastRun) {
    return (
      <span data-testid="freshness-pill" className={`rounded-pill px-3 py-1.5 text-sm ${TONES.none}`}>
        ● {sync.isSuccess ? 'No pipeline run yet' : 'Checking feeds…'}
      </span>
    )
  }
  const minutes = minutesBetween(lastRun, clock.data.now_utc)
  const tone = freshnessTone(minutes)
  const lead = tone === 'green' ? 'All feeds current' : 'Feeds stale'
  return (
    <span data-testid="freshness-pill" data-tone={tone} className={`rounded-pill px-3 py-1.5 text-sm ${TONES[tone]}`}>
      ● {lead} — last sync {formatFeedAge(minutes)} ago
    </span>
  )
}
