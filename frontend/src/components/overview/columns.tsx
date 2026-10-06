import type { ReactNode } from 'react'
import type { Row } from '../../api/queries'
import type { Terms } from '../../hooks/useTerms'
import { formatDate } from '../../lib/format'
import { dash, expectedText, slaDeadline, statusOf } from '../../lib/status'
import type { Column } from '../datatable/DataTable'
import { BookmarkStar } from '../table/cells'
import type { WindowName } from '../../state/batch-view'
import { AdjustedDate, DotButton, ExpectedCell, MaterialCell, SlaDeadline, StageBadge, StatusCell, SystemNeedBy } from './cells'

export interface OverviewColumnDeps {
  terms: Terms
  stageIndex: Map<string, number>
  canEdit: boolean
  bookmarks: ReadonlySet<string>
  onToggleBookmark?: (rowKey: string, on: boolean) => void
  onOpenRow?: (rowKey: string) => void
  /** Open one of the batch windows from a cell (F19-FR-07): the dots, the sample badge, the status bubble, the adjusted date. */
  onOpenWindow?: (win: WindowName, rowKey: string) => void
  /** The `⋯` menu of a row (F18-FR-08). */
  actions?: (row: Row) => ReactNode
}

const title = (value: string | null) =>
  value ? value.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ') : ''
const date = (value: string | null) => (value ? formatDate(value) : '—')
const LATE_LAST = '9999-12-31'

/**
 * The 20 columns of the pipeline table, in the order of F18-FR-02: the first 16 are on by default and the last
 * four (First QC Date, Goods Receipt Date, <lims> Approved Date, Usage Decision Date) are off.
 */
export function overviewColumns(deps: OverviewColumnDeps): Column<Row>[] {
  const { terms, stageIndex, canEdit, bookmarks, onToggleBookmark, onOpenRow, onOpenWindow, actions } = deps
  return [
    {
      id: 'material',
      header: 'Material',
      text: (row) => [row.material_no, row.material_desc, row.supplier_batch].filter(Boolean).join(' '),
      sortValue: (row) => row.material_no,
      cell: (row, { hl }) => (
        <MaterialCell
          row={row}
          terms={terms}
          hl={hl}
          star={
            onToggleBookmark ? (
              <BookmarkStar rowKey={row.row_key} on={bookmarks.has(row.row_key)} onToggle={onToggleBookmark} />
            ) : null
          }
          actions={actions?.(row)}
        />
      ),
    },
    { id: 'campaign', header: 'Campaign', text: (row) => dash(row.campaign), cell: (row, { hl }) => hl(dash(row.campaign)) },
    { id: 'class', header: 'Class', text: (row) => title(row.material_class), cell: (row, { hl }) => hl(title(row.material_class)) },
    {
      id: 'batch',
      header: 'Batch',
      text: (row) => row.batch_no,
      cell: (row, { hl }) => (
        <button
          type="button"
          tabIndex={-1}
          className="font-medium text-accent hover:underline"
          onClick={(event) => {
            event.stopPropagation()
            onOpenRow?.(row.row_key)
          }}
        >
          {hl(row.batch_no)}
        </button>
      ),
    },
    { id: 'lot', header: 'Lot #', text: (row) => row.inspection_lot_no, cell: (row, { hl }) => hl(row.inspection_lot_no) },
    { id: 'inbound', header: 'Inbound', text: (row) => row.inbound_light ?? 'grey', cell: (row) => <DotButton colour={row.inbound_light} what="Inbound check" label="inbound" onOpen={onOpenWindow && (() => onOpenWindow('inbound', row.row_key))} /> },
    { id: 'deviation', header: 'Deviation', text: (row) => row.deviation_light ?? 'grey', cell: (row) => <DotButton colour={row.deviation_light} what="Deviations" label="quality" onOpen={onOpenWindow && (() => onOpenWindow('quality', row.row_key))} /> },
    {
      id: 'location',
      header: 'Location',
      text: (row) => (row.storage_location ? `${row.storage_location} ${row.location_type === '3pl' ? '3PL' : 'Onsite'}` : '—'),
      cell: (row, { hl }) => hl(row.storage_location ? `${row.storage_location} ${row.location_type === '3pl' ? '3PL' : 'Onsite'}` : '—'),
    },
    {
      id: 'stage',
      header: 'Stage',
      text: (row) => row.stage_label,
      sortValue: (row) => stageIndex.get(row.stage_key) ?? 0,
      cell: (row) => (
        <StageBadge row={row} index={stageIndex.get(row.stage_key) ?? 0} onOpenSamples={onOpenWindow && (() => onOpenWindow('samples', row.row_key))} />
      ),
    },
    {
      id: 'system_need_by',
      header: 'System Needs-By',
      text: (row) => date(row.system_need_by_locked),
      sortValue: (row) => row.system_need_by_locked ?? LATE_LAST,
      cell: (row) => <SystemNeedBy row={row} />,
    },
    {
      id: 'adjusted',
      header: 'Adjusted Date',
      text: (row) => (row.adjusted_need_by_date ? date(row.adjusted_need_by_date) : '+ set date'),
      sortValue: (row) => row.adjusted_need_by_date ?? LATE_LAST,
      cell: (row) => <AdjustedDate row={row} canEdit={canEdit} onEdit={onOpenWindow && ((key) => onOpenWindow('needby', key))} />,
    },
    {
      id: 'sla_deadline',
      header: 'SLA Deadline',
      text: (row) => date(slaDeadline(row)),
      sortValue: (row) => slaDeadline(row) ?? LATE_LAST,
      cell: (row) => <SlaDeadline row={row} />,
    },
    {
      id: 'next_inspection',
      header: 'Next Inspection',
      text: (row) => date(row.next_inspection_date),
      sortValue: (row) => row.next_inspection_date ?? LATE_LAST,
      cell: (row, { hl }) => hl(date(row.next_inspection_date)),
    },
    {
      id: 'days',
      header: 'Days In Stage',
      text: (row) => (row.days_in_stage === null ? '—' : `${row.days_in_stage}d`),
      sortValue: (row) => row.days_in_stage ?? -1,
      cell: (row, { hl }) => hl(row.days_in_stage === null ? '—' : `${row.days_in_stage}d`),
    },
    {
      id: 'status',
      header: 'Status',
      text: (row) => statusOf(row).text,
      sortValue: (row) => row.plan.days_remaining ?? Number.MAX_SAFE_INTEGER,
      cell: (row, { hl }) => <StatusCell row={row} hl={hl} onOpenStatus={onOpenWindow && (() => onOpenWindow('status', row.row_key))} />,
    },
    {
      id: 'expected',
      header: 'Expected Completion',
      text: expectedText,
      sortValue: (row) => row.plan.expected_completion ?? LATE_LAST,
      cell: (row, { hl }) => <ExpectedCell row={row} hl={hl} />,
    },
    { id: 'first_qc', header: 'First QC Date', defaultHidden: true, text: (row) => date(row.qc_testing_entry), sortValue: (row) => row.qc_testing_entry ?? LATE_LAST, cell: (row, { hl }) => hl(date(row.qc_testing_entry)) },
    { id: 'gr_date', header: 'Goods Receipt Date', defaultHidden: true, text: (row) => date(row.gr_date), sortValue: (row) => row.gr_date ?? LATE_LAST, cell: (row, { hl }) => hl(date(row.gr_date)) },
    {
      id: 'lims_approved',
      header: `${terms.lims} Approved Date`,
      defaultHidden: true,
      text: (row) => date(row.lims_approved_date),
      sortValue: (row) => row.lims_approved_date ?? LATE_LAST,
      cell: (row, { hl }) => hl(date(row.lims_approved_date)),
    },
    { id: 'ud_date', header: 'Usage Decision Date', defaultHidden: true, text: (row) => date(row.ud_date), sortValue: (row) => row.ud_date ?? LATE_LAST, cell: (row, { hl }) => hl(date(row.ud_date)) },
  ]
}
