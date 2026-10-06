import type { RowDetail } from '../../api/queries'
import { formatDate } from '../../lib/format'
import { saveBlob } from '../../lib/download'
import { lotList, milestones, timeline, timelineCsv, totalDays } from '../../lib/history'

/** The drawer's history sections (F19-FR-01, OQ-116): summary, milestone dates, stage timeline, other lots, export. */

interface SummaryProps {
  detail: RowDetail
  today: string
  stageChip: React.ReactNode
  tags: React.ReactNode
}

/** MATERIAL / CURRENT STAGE / TOTAL DAYS / NEXT INSPECTION, with the lot's tags below. */
export function HistorySummary({ detail, today, stageChip, tags }: SummaryProps) {
  const total = totalDays(detail, today)
  return (
    <div className="space-y-2">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-card bg-panel p-4 text-[13px]" data-testid="history-summary">
        <div>
          <dt className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Material</dt>
          <dd className="mt-0.5">{detail.material_desc ?? detail.material_no}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Current stage</dt>
          <dd className="mt-0.5 flex items-center gap-1.5 uppercase">{stageChip}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Total days</dt>
          <dd className="mt-0.5" data-testid="total-days">
            {total ? (
              <span className={total.over ? 'font-semibold text-red-700' : 'font-semibold text-emerald-700'} data-over={total.over ? 'true' : 'false'}>
                {total.days}d / {total.target}d target
              </span>
            ) : (
              '—'
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Next inspection</dt>
          <dd className="mt-0.5">{formatDate(detail.next_inspection_date)}</dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-1.5 empty:hidden">{tags}</div>
    </div>
  )
}

/** Goods receipt, call-off target, first sampled, sample shipped and usage decision, each with its gap. */
export function MilestoneDates({ detail }: { detail: RowDetail }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px]" data-testid="milestones">
      {milestones(detail).map((milestone) => (
        <div key={milestone.label} data-state={milestone.state}>
          <dt className="text-slate-500">{milestone.label}</dt>
          <dd>
            {milestone.state === 'dated' ? (
              <>
                {formatDate(milestone.date)}
                {milestone.gap && (
                  <span className="ml-1.5 text-xs text-slate-500">
                    +{milestone.gap.days}d from {milestone.gap.from}
                  </span>
                )}
              </>
            ) : milestone.state === 'pending' ? (
              <span className="text-slate-400 italic">(pending)</span>
            ) : (
              '—'
            )}
          </dd>
        </div>
      ))}
    </dl>
  )
}

const DOT = { green: 'bg-emerald-600', red: 'bg-red-600', blue: 'bg-sky-500' }

interface TimelineProps {
  detail: RowDetail
  today: string
  stageLabel: (key: string) => string
}

/** One entry per stage reached: a green, red or blue dot, entered and exited dates, the SLA and the days taken. */
export function StageTimeline({ detail, today, stageLabel }: TimelineProps) {
  const entries = timeline(detail, today)
  return (
    <div data-testid="stage-timeline">
      <ol className="space-y-1.5 text-[13px]">
        {entries.map((entry) => (
          <li
            key={entry.stage_key}
            data-tone={entry.tone}
            className={`flex items-center gap-2 rounded-chip px-2 py-1.5 ${entry.tone === 'blue' ? 'bg-sky-50' : ''}`}
          >
            <span aria-hidden className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT[entry.tone]}`} />
            <span className="w-24 shrink-0 font-medium">{stageLabel(entry.stage_key)}</span>
            <span className="flex-1 text-slate-600">
              Entered {formatDate(entry.entered)} ·{' '}
              {entry.exited ? `Exited ${formatDate(entry.exited)}` : 'In progress'} · SLA: {entry.sla}d
              {entry.tone === 'red' && <span className="ml-1 text-red-700">+{entry.overBy}d over</span>}
            </span>
            <span className={`shrink-0 font-semibold ${entry.overBy > 0 ? 'text-red-700' : ''}`}>{entry.days}d</span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs text-slate-500">Derived from pipeline facts; a stage entered and left on the same day shows 0d.</p>
    </div>
  )
}

interface LotsProps {
  detail: RowDetail
  stageLabel: (key: string) => string
  onOpen: (rowKey: string) => void
}

/** Every lot of the batch, oldest first; the open lot is marked "current" and is not a link (OQ-113). */
export function OtherLots({ detail, stageLabel, onOpen }: LotsProps) {
  return (
    <ol className="space-y-1" data-testid="lot-list">
      {lotList(detail).map((lot) => (
        <li key={lot.rowKey} data-testid="lot-item">
          <button
            type="button"
            aria-current={lot.current}
            disabled={lot.current}
            onClick={() => onOpen(lot.rowKey)}
            className={`flex w-full items-center justify-between rounded-chip border px-3 py-1.5 text-left text-[13px] ${lot.current ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 hover:bg-slate-50'}`}
          >
            <span>
              <span className="font-medium">{lot.label}</span>
              <span className="ml-2 text-slate-500">lot {lot.lotNo}</span>
              {lot.current ? <span className="ml-2 text-xs font-semibold text-indigo-700">(current)</span> : <span className="ml-2 text-xs text-accent">▸ open</span>}
            </span>
            <span>{stageLabel(lot.stageKey)}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}

/** Export the timeline as CSV (built here, no endpoint). */
export function ExportTimeline({ detail, today, stageLabel }: TimelineProps) {
  return (
    <button
      type="button"
      className="rounded-chip border border-slate-300 px-3 py-1.5 text-[13px] hover:bg-slate-50"
      onClick={() =>
        saveBlob(
          new Blob([timelineCsv(timeline(detail, today), stageLabel)], { type: 'text/csv' }),
          `r2r-timeline-${detail.batch_no}-${detail.inspection_lot_no}.csv`,
        )
      }
    >
      ↓ Export
    </button>
  )
}
