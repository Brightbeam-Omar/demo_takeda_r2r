import { useInsights, useReference } from '../../api/queries'
import type { Insights } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { EmptyState, ErrorState, Skeleton } from '../common/States'
import { DataTable, type Column } from '../common/DataTable'
import { Modal } from '../common/Modal'

type Entry = Insights['rows'][number]

/** Green under 2 days, amber 2–5, red over 5 (F16-FR-09). A gap is at least a day (OQ-088). */
export function gapTone(days: number): 'green' | 'amber' | 'red' {
  if (days < 2) return 'green'
  return days <= 5 ? 'amber' : 'red'
}

const TONE = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  amber: 'border-amber-200 bg-amber-50 text-amber-800',
  red: 'border-red-200 bg-red-50 text-red-800',
}

export function GapChip({ days }: { days: number }) {
  return (
    <span data-tone={gapTone(days)} className={`inline-block rounded-pill border px-2 py-0.5 text-xs font-semibold ${TONE[gapTone(days)]}`}>
      {days}d
    </span>
  )
}

interface Props {
  open: boolean
  onClose: () => void
  /** The Overview filters except stage, in the API's form. */
  params: URLSearchParams
}

export function InsightsWindow({ open, onClose, params }: Props) {
  const terms = useTerms()
  const reference = useReference()
  const insights = useInsights(params, open)
  const total = insights.data?.total ?? 0
  const qaRelease = String((reference.data?.stages ?? []).find((stage) => stage.stage_key === 'qa_release')?.label ?? 'QA Release')
  const columns: Column<Entry>[] = [
    { id: 'batch', header: 'Batch', cell: (r) => r.batch_no, text: (r) => r.batch_no },
    {
      id: 'material',
      header: 'Material',
      cell: (r) => (
        <>
          <div>{r.material_no}</div>
          <div className="text-xs text-slate-500">{r.material_desc}</div>
        </>
      ),
      text: (r) => `${r.material_no} ${r.material_desc ?? ''}`,
    },
    { id: 'stage', header: 'Stage', cell: (r) => r.stage_label, text: (r) => r.stage_label },
    { id: 'gap', header: 'Days Gap', cell: (r) => <GapChip days={r.days_gap} />, text: (r) => `${r.days_gap}d`, sortValue: (r) => r.days_gap },
  ]
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${terms.insights_banner} — ${total} affected ${total === 1 ? 'batch' : 'batches'}`}
      description={`Batches where ${terms.lims} is approved but ${terms.erp} has not received the result. Flagged after ${reference.data?.air_gap_threshold_hours ?? 24}+ hours — each day erodes the ${qaRelease} SLA. Sorted worst-first.`}
    >
      {insights.isError ? (
        <ErrorState what="the insights" error={insights.error} onRetry={() => void insights.refetch()} />
      ) : !insights.data ? (
        <Skeleton label="insights" height="h-40" />
      ) : insights.data.rows.length === 0 ? (
        <EmptyState>{`No ${terms.insights_banner} in this period.`}</EmptyState>
      ) : (
        <DataTable rows={insights.data.rows} columns={columns} exportName="insights" rowKey={(r) => r.row_key} />
      )}
    </Modal>
  )
}
