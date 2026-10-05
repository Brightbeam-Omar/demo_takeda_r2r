import type { Row, RowDetail } from '../../api/queries'
import { daysBetween, formatShortDate } from '../../lib/format'

interface Sla {
  stage_key: string
  sla_days: number
}

interface Props {
  detail: RowDetail
  today: string
  stageLabel: (key: string) => string
}

/** Stage entry and exit with the days taken against the SLA for this lot (F11-FR-01, OQ-074). */
export function StageTimeline({ detail, today, stageLabel }: Props) {
  const facts = detail.facts as Record<string, unknown>
  const slas = (facts.applicable_sla_json ?? []) as Sla[]
  const effective = detail.plan.effective_slas as Record<string, number>
  return (
    <table className="w-full text-left text-[13px]" data-testid="stage-timeline">
      <thead className="text-xs text-slate-500 uppercase">
        <tr>
          <th className="py-1 font-medium">Stage</th>
          <th className="font-medium">Entered</th>
          <th className="font-medium">Left</th>
          <th className="font-medium">Days</th>
          <th className="font-medium">SLA</th>
        </tr>
      </thead>
      <tbody>
        {slas.map(({ stage_key, sla_days }) => {
          const entry = facts[`${stage_key}_entry`] as string | null
          const exit = facts[`${stage_key}_exit`] as string | null
          const days = entry ? daysBetween(entry, exit ?? today) : null
          const compressed = effective[stage_key] !== undefined && effective[stage_key] !== sla_days
          const over = days !== null && days > sla_days
          const current = detail.stage_key === stage_key
          return (
            <tr key={stage_key} className={`border-t border-slate-100 ${current ? 'bg-indigo-50/60 font-medium' : ''}`}>
              <td className="py-1.5">{stageLabel(stage_key)}</td>
              <td>{formatShortDate(entry)}</td>
              <td>{entry ? (exit ? formatShortDate(exit) : 'in progress') : '–'}</td>
              <td className={over ? 'text-red-700' : ''}>{days === null ? '–' : `${days} d`}</td>
              <td>
                {sla_days} d{compressed ? <span className="text-slate-500"> → {effective[stage_key]} d</span> : null}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

interface LotsProps {
  detail: RowDetail
  stageLabel: (key: string) => string
  onOpen: (rowKey: string) => void
}

/** The initial lot and each re-evaluation of the same batch, oldest first (the current one marked). */
export function SiblingLots({ detail, stageLabel, onOpen }: LotsProps) {
  const lots = [detail as unknown as Row, ...detail.siblings].sort(
    (a, b) => (a.lot_type === '01' ? 0 : 1) - (b.lot_type === '01' ? 0 : 1) || a.inspection_lot_no.localeCompare(b.inspection_lot_no),
  )
  let reeval = 0
  return (
    <ol className="space-y-1" data-testid="lot-list">
      {lots.map((lot) => {
        const label = lot.lot_type === '01' ? 'Initial' : `Re-eval ${++reeval}`
        const here = lot.row_key === detail.row_key
        return (
          <li key={lot.row_key} data-testid="lot-item">
            <button
              type="button"
              aria-current={here}
              disabled={here}
              onClick={() => onOpen(lot.row_key)}
              className={`flex w-full items-center justify-between rounded-chip border px-3 py-1.5 text-left text-[13px] ${here ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 hover:bg-slate-50'}`}
            >
              <span>
                <span className="font-medium">{label}</span>
                <span className="ml-2 text-slate-500">lot {lot.inspection_lot_no}</span>
                {here ? <span className="ml-2 text-xs text-indigo-700">(this lot)</span> : null}
              </span>
              <span>{stageLabel(lot.stage_key)}</span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
