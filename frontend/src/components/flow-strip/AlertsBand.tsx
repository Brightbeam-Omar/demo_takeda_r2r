import type { Overview } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import type { Filters } from '../../state/url-filters'

type Alert = Overview['alerts'][number]

const TITLES: Record<Alert['kind'], string> = {
  air_gap: 'Air gap',
  late: 'Late',
  on_hold: 'On hold',
  rejected: 'Rejected',
}

/** The flags a click filters the table to. */
const FLAGS: Record<Alert['kind'], string[]> = {
  air_gap: ['air_gap'],
  late: ['late'],
  on_hold: ['on_hold'],
  rejected: ['ud_rejected', 'lims_rejected'],
}

const TONE: Record<Alert['kind'], string> = {
  air_gap: 'border-red-200 bg-red-50 text-red-800',
  late: 'border-red-200 bg-red-50 text-red-800',
  on_hold: 'border-amber-200 bg-amber-50 text-amber-800',
  rejected: 'border-red-200 bg-red-50 text-red-800',
}

interface Props {
  alerts: Alert[]
  onFilter: (patch: Partial<Filters>) => void
}

/** F10-FR-06. Hidden when every count is zero. */
export function AlertsBand({ alerts, onFilter }: Props) {
  const terms = useTerms()
  const active = alerts.filter((alert) => alert.count > 0)
  if (active.length === 0) return null
  return (
    <section aria-label="Alerts" className="flex flex-wrap gap-3">
      {active.map((alert) => (
        <button
          key={alert.kind}
          type="button"
          data-testid={`alert-${alert.kind}`}
          className={`rounded-card border px-4 py-2 text-left text-sm ${TONE[alert.kind]} hover:shadow`}
          onClick={() => onFilter({ flags: FLAGS[alert.kind] })}
        >
          <span className="font-semibold">
            {TITLES[alert.kind]}: {alert.count}
          </span>
          {alert.kind === 'air_gap' && alert.rows.length > 0 && (
            <span className="ml-2 text-xs">
              {alert.rows.map((row) => `${row.batch_no} (${row.air_gap_hours} h)`).join(' · ')}
            </span>
          )}
          {alert.kind === 'rejected' && (
            <span className="ml-2 text-xs">
              {alert.detail.ud_rejected ?? 0} usage decision · {alert.detail.lims_rejected ?? 0} {terms.lims}
            </span>
          )}
        </button>
      ))}
    </section>
  )
}
