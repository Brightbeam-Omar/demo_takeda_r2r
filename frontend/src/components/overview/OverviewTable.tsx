import { useMemo, type ReactNode } from 'react'
import type { Row } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { DataTable, type ColumnFilterRequest } from '../datatable/DataTable'
import { overviewColumns, type OverviewColumnDeps } from './columns'

interface Props extends Omit<OverviewColumnDeps, 'terms'> {
  rows: Row[]
  changedKeys: ReadonlySet<string>
  search: { value: string; onChange: (value: string) => void }
  /** Keeps the column choice per user (F18-FR-02). */
  columnsKey: string
  toolbarExtra?: ReactNode
  onRowKey?: (key: string, row: Row) => void
  /** Fills a header filter box from outside, e.g. the batch number when the drawer closes (F19-FR-01). */
  filterRequest?: ColumnFilterRequest | null
}

const RED = '#DC2626'
const TINT = '#FEF2F2'

/** Late, rejected, on hold or air gap: the exception groups of 03 section 5.5 (F18-FR-04). ERP-blocked is a tag only. */
export const isException = (row: Row) => row.plan.late || row.flags.ud_rejected || row.flags.on_hold || row.flags.air_gap

const HINT = 'Keyboard: Tab to focus the table · ↑ ↓ move between rows · Enter opens the batch drawer · B bookmarks the row'

/** The Overview's "Pipeline — Exceptions First" table (F18). */
export function OverviewTable({ rows, changedKeys, search, columnsKey, toolbarExtra, onRowKey, filterRequest, ...deps }: Props) {
  const terms = useTerms()
  const { stageIndex, canEdit, bookmarks, onToggleBookmark, onOpenRow, onOpenWindow, actions } = deps
  const columns = useMemo(
    () => overviewColumns({ terms, stageIndex, canEdit, bookmarks, onToggleBookmark, onOpenRow, onOpenWindow, actions }),
    [terms, stageIndex, canEdit, bookmarks, onToggleBookmark, onOpenRow, onOpenWindow, actions],
  )
  // A batch with a re-evaluation lot appears twice, so distinct batches are counted on material + batch (03 section 3).
  const countSuffix = (shown: Row[]) => {
    const batches = new Set(shown.map((row) => `${row.material_no}|${row.batch_no}`)).size
    return ` (${batches} ${batches === 1 ? 'batch' : 'batches'})`
  }
  return (
    <DataTable
      rows={rows}
      columns={columns}
      rowKey={(row) => row.row_key}
      exportName="r2r-overview"
      unit={['lot', 'lots']}
      countSuffix={countSuffix}
      columnsKey={columnsKey}
      search={search}
      toolbarExtra={toolbarExtra}
      rowTestId="batch-row"
      rowClassName={(row) => (changedKeys.has(row.row_key) ? 'row-changed' : '')}
      rowTint={(row) => (isException(row) ? TINT : undefined)}
      rowAccent={(row) => (isException(row) ? RED : undefined)}
      onRowOpen={(row) => onOpenRow?.(row.row_key)}
      onRowKey={onRowKey}
      filterRequest={filterRequest}
      keyboardHint={HINT}
      ariaLabel="Pipeline — Exceptions First"
    />
  )
}
