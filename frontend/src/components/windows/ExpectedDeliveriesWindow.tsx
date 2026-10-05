import { useExpectedDeliveries } from '../../api/queries'
import type { Deliveries } from '../../api/queries'
import { formatDate } from '../../lib/format'
import { EmptyState, ErrorState, Skeleton } from '../common/States'
import { DataTable, type Column } from '../common/DataTable'
import { Modal } from '../common/Modal'

type Entry = Deliveries['rows'][number]

interface Props {
  open: boolean
  onClose: () => void
  /** The Overview's type, class, campaign and period filters in the API's form (stage and tags never apply). */
  params: URLSearchParams
}

/** F17-FR-05: the open purchase-order lines behind the Stage 0 card. */
export function ExpectedDeliveriesWindow({ open, onClose, params }: Props) {
  const deliveries = useExpectedDeliveries(params, open)
  const columns: Column<Entry>[] = [
    { id: 'po', header: 'PO', cell: (r) => r.ebeln, text: (r) => r.ebeln },
    { id: 'line', header: 'Line', cell: (r) => r.ebelp, text: (r) => r.ebelp },
    {
      id: 'material',
      header: 'Material',
      cell: (r) => (
        <>
          <div>{r.material_no}</div>
          <div className="text-xs text-ink-2">{r.material_desc}</div>
        </>
      ),
      text: (r) => `${r.material_no ?? ''} ${r.material_desc ?? ''}`,
    },
    { id: 'supplier', header: 'Supplier', cell: (r) => r.supplier_name ?? '–', text: (r) => r.supplier_name ?? '' },
    {
      id: 'scheduled',
      header: 'Scheduled',
      cell: (r) => formatDate(r.scheduled_date),
      text: (r) => formatDate(r.scheduled_date),
      sortValue: (r) => Date.parse(r.scheduled_date ?? '') || 0,
    },
    {
      id: 'quantity',
      header: 'Quantity',
      cell: (r) => (r.quantity ?? 0).toLocaleString('en-GB'),
      text: (r) => String(r.quantity ?? ''),
      sortValue: (r) => r.quantity ?? 0,
    },
    {
      id: 'location',
      header: 'Planned Location',
      cell: (r) => r.planned_location ?? '–',
      text: (r) => r.planned_location ?? '',
    },
    {
      id: 'overdue',
      header: 'Status',
      cell: (r) =>
        r.overdue ? (
          <span className="inline-block rounded-pill border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-800">Overdue</span>
        ) : (
          <span className="text-ink-2">Due</span>
        ),
      text: (r) => (r.overdue ? 'Overdue' : 'Due'),
    },
  ]
  const total = deliveries.data?.count ?? 0
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Expected Deliveries — ${total} open PO ${total === 1 ? 'line' : 'lines'}`}
      description="Purchase-order lines not yet received. They become batches at goods receipt, so they are never added to the pipeline total."
    >
      {deliveries.isError ? (
        <ErrorState what="the expected deliveries" error={deliveries.error} onRetry={() => void deliveries.refetch()} />
      ) : !deliveries.data ? (
        <Skeleton label="expected deliveries" height="h-40" />
      ) : deliveries.data.rows.length === 0 ? (
        <EmptyState>No open PO lines in this period.</EmptyState>
      ) : (
        <DataTable rows={deliveries.data.rows} columns={columns} exportName="expected-deliveries" rowKey={(r) => `${r.ebeln}|${r.ebelp}`} />
      )}
    </Modal>
  )
}
