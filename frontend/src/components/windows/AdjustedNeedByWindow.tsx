import { useAdjusted } from '../../api/queries'
import type { Adjusted } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { formatDate } from '../../lib/format'
import { EmptyState, ErrorState, Skeleton } from '../common/States'
import { DataTable, type Column } from '../common/DataTable'
import { Modal } from '../common/Modal'

type Entry = Adjusted['rows'][number]

/** `+7` green when pushed later, `−7` red when pulled earlier (F16-FR-07). */
export function Delta({ days }: { days: number | null }) {
  if (days === null) return <span>–</span>
  if (days === 0) return <span>0</span>
  return days > 0 ? (
    <span className="font-semibold text-emerald-700">+{days}</span>
  ) : (
    <span className="font-semibold text-red-700">−{Math.abs(days)}</span>
  )
}

interface Props {
  open: boolean
  onClose: () => void
  /** The Overview filters except stage, in the API's form. */
  params: URLSearchParams
}

export function AdjustedNeedByWindow({ open, onClose, params }: Props) {
  const terms = useTerms()
  const adjusted = useAdjusted(params, open)
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
    { id: 'system', header: `${terms.erp} Date`, cell: (r) => formatDate(r.system_need_by_date), text: (r) => formatDate(r.system_need_by_date), sortValue: (r) => Date.parse(r.system_need_by_date ?? '') || 0 },
    { id: 'adjusted', header: 'Adjusted Date', cell: (r) => formatDate(r.adjusted_date), text: (r) => formatDate(r.adjusted_date), sortValue: (r) => Date.parse(r.adjusted_date) },
    { id: 'delta', header: 'Δ Days', cell: (r) => <Delta days={r.delta_days} />, text: (r) => (r.delta_days === null ? '' : r.delta_days > 0 ? `+${r.delta_days}` : `${r.delta_days}`), sortValue: (r) => r.delta_days ?? 0 },
    { id: 'reason', header: 'Reason', cell: (r) => r.reason_label ?? '–', text: (r) => r.reason_label ?? '' },
    { id: 'set_by', header: 'Set By', cell: (r) => r.set_by, text: (r) => r.set_by },
  ]
  return (
    <Modal open={open} onClose={onClose} title="Adjusted Needs-by Dates — Planner Overrides">
      {adjusted.isError ? (
        <ErrorState what="the adjusted needs-by dates" error={adjusted.error} onRetry={() => void adjusted.refetch()} />
      ) : !adjusted.data ? (
        <Skeleton label="adjusted needs-by dates" height="h-40" />
      ) : adjusted.data.rows.length === 0 ? (
        <EmptyState>No adjusted needs-by dates in this period.</EmptyState>
      ) : (
        <DataTable rows={adjusted.data.rows} columns={columns} exportName="adjusted-needs-by-dates" rowKey={(r) => r.row_key} />
      )}
    </Modal>
  )
}
