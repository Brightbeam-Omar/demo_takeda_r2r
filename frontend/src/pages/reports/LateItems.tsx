import { useMemo } from 'react'
import { useReport } from '../../api/queries'
import { DataTable, type Column } from '../../components/datatable/DataTable'
import { ErrorState, Skeleton } from '../../components/common/States'
import type { LateReport } from '../../lib/reports'

type Item = LateReport['items'][number]

const COLUMNS: Column<Item>[] = [
  {
    id: 'material',
    header: 'Material',
    text: (row) => `${row.material_no} ${row.material_desc ?? ''} ${row.batch_no}`.trim(),
    cell: (row) => (
      <span>
        <span className="font-medium">{row.material_no}</span>
        <span className="block text-xs text-ink-2">
          {row.material_desc ?? ''} · {row.batch_no}
        </span>
      </span>
    ),
  },
  { id: 'campaign', header: 'Campaign', text: (row) => row.campaign ?? '–', cell: (row) => row.campaign ?? '–' },
  { id: 'stage', header: 'Current Stage', text: (row) => row.stage_label, cell: (row) => row.stage_label },
  { id: 'metric', header: 'Metric Breached', text: (row) => row.metric_breached ?? '—', cell: (row) => row.metric_breached ?? '—' },
  {
    id: 'days',
    header: 'Days Over SLA',
    text: (row) => `${row.days_over_sla}d`,
    sortValue: (row) => row.days_over_sla,
    cell: (row) => <span className="font-semibold text-rag-red tabular-nums">+{row.days_over_sla}d</span>,
  },
  { id: 'reason', header: 'Late-Reason Category', text: (row) => row.late_reason ?? '—', cell: (row) => row.late_reason ?? '—' },
]

/** The rows that are late now, worst first. Not narrowed by the Overview filters, period or year (OQ-123). */
export function LateItems({ params }: { params: URLSearchParams }) {
  const report = useReport<LateReport>('late', params)
  const rows = useMemo(() => report.data?.items ?? [], [report.data])
  if (report.isError) return <ErrorState what="the late items" error={report.error} onRetry={() => void report.refetch()} />
  if (!report.data) return <Skeleton label="the late items" height="h-64" />
  return (
    <div data-testid="report-late" className="space-y-2">
      <p className="text-sm text-ink-2" data-testid="late-count">
        {report.data.count} late {report.data.count === 1 ? 'row' : 'rows'}, worst first.
      </p>
      <DataTable
        rows={rows}
        columns={COLUMNS}
        rowKey={(row) => row.row_key}
        exportName="late-items"
        unit={['row', 'rows']}
        headerFilters
        defaultPageSize={25}
        empty="Nothing is late right now."
        rowTestId="late-row"
        ariaLabel="Late items"
      />
    </div>
  )
}
