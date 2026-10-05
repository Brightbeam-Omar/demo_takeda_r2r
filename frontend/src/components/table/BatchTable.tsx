import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useMemo, useRef, useState, type ReactNode } from 'react'
import type { Row } from '../../api/queries'
import {
  AdjustedNeedBy,
  LocationCell,
  Light,
  MaterialCell,
  RagCell,
  StageChip,
  StatusCell,
  SystemNeedBy,
} from './cells'

const ROW_HEIGHT = 36
const helper = createColumnHelper<Row>()
// Minimum px and a share of any spare width per column; at 1440 px the whole table fits without scrolling.
const MIN_WIDTH = 1108
const WIDTHS: Record<string, string> = {
  material: 'minmax(190px, 2.4fr)',
  campaign: 'minmax(90px, 1fr)',
  batch: 'minmax(64px, 0.7fr)',
  location: 'minmax(84px, 1fr)',
  inbound: 'minmax(56px, 0.5fr)',
  deviation: 'minmax(70px, 0.6fr)',
  stage: 'minmax(100px, 1.1fr)',
  system_need_by: 'minmax(84px, 0.9fr)',
  adjusted_need_by: 'minmax(100px, 1fr)',
  expected: 'minmax(140px, 1.4fr)',
  days: 'minmax(60px, 0.6fr)',
  status: 'minmax(70px, 0.7fr)',
}

interface Props {
  rows: Row[]
  stageIndex: Map<string, number>
  canEdit: boolean
  changedKeys: ReadonlySet<string>
  toolbar?: ReactNode
}

/** A text for the per-column filter and the sort, taken from what the cell shows. */
const text = (value: string | number | null | undefined) => (value === null || value === undefined ? '' : String(value))

export function BatchTable({ rows, stageIndex, canEdit, changedKeys, toolbar }: Props) {
  // Unsorted = the server's exceptions-first order (F09-FR-02).
  const [sorting, setSorting] = useState<SortingState>([])
  const scroller = useRef<HTMLDivElement>(null)

  const columns = useMemo(
    () => [
      helper.accessor((row) => `${row.material_no} ${row.material_desc ?? ''}`, {
        id: 'material',
        header: 'Material',
        cell: ({ row }) => <MaterialCell row={row.original} />,
      }),
      helper.accessor((row) => text(row.campaign), { id: 'campaign', header: 'Campaign' }),
      helper.accessor('batch_no', { id: 'batch', header: 'Batch' }),
      helper.accessor((row) => text(row.storage_location) + text(row.location_type), {
        id: 'location',
        header: 'Location',
        cell: ({ row }) => <LocationCell row={row.original} />,
      }),
      helper.accessor((row) => text(row.inbound_light), {
        id: 'inbound',
        header: 'Inbound',
        cell: ({ row }) => <Light colour={row.original.inbound_light} what="Inbound check" />,
      }),
      helper.accessor((row) => text(row.deviation_light), {
        id: 'deviation',
        header: 'Deviation',
        cell: ({ row }) => <Light colour={row.original.deviation_light} what="Deviations" />,
      }),
      helper.accessor('stage_label', {
        id: 'stage',
        header: 'Stage',
        cell: ({ row }) => (
          <StageChip label={row.original.stage_label} index={stageIndex.get(row.original.stage_key) ?? 0} />
        ),
      }),
      helper.accessor((row) => text(row.system_need_by_locked), {
        id: 'system_need_by',
        header: 'System need-by',
        cell: ({ row }) => <SystemNeedBy row={row.original} />,
      }),
      helper.accessor((row) => text(row.adjusted_need_by_date), {
        id: 'adjusted_need_by',
        header: 'Adjusted need-by',
        cell: ({ row }) => <AdjustedNeedBy row={row.original} canEdit={canEdit} />,
      }),
      helper.accessor((row) => text(row.plan.expected_completion), {
        id: 'expected',
        header: 'Expected completion',
        cell: ({ row }) => <RagCell row={row.original} />,
      }),
      helper.accessor((row) => row.days_in_stage ?? -1, {
        id: 'days',
        header: 'Days in stage',
        cell: ({ row }) => (row.original.days_in_stage === null ? '–' : `${row.original.days_in_stage} d`),
        filterFn: (row, _id, value: string) => text(row.original.days_in_stage).includes(value),
      }),
      helper.accessor((row) => text((row.manual_status as { rag?: string } | null)?.rag), {
        id: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusCell row={row.original} />,
      }),
    ],
    [stageIndex, canEdit],
  )

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table v8 hands back unmemoised functions; nothing here depends on their identity
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    defaultColumn: {
      filterFn: (row, id, value: string) => text(row.getValue(id)).toLowerCase().includes(value.toLowerCase()),
    },
  })

  const tableRows = table.getRowModel().rows
  const virtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  })

  const widths = table
    .getVisibleLeafColumns()
    .map((column) => WIDTHS[column.id] ?? 'minmax(100px, 1fr)')
    .join(' ')
  const grid = { display: 'grid', gridTemplateColumns: widths } as const

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500" data-testid="row-count">
          {tableRows.length} {tableRows.length === 1 ? 'batch' : 'batches'}
        </span>
        {toolbar}
      </div>
      <div
        ref={scroller}
        role="table"
        aria-label="Batches"
        aria-rowcount={tableRows.length}
        className="h-[28rem] overflow-auto rounded-card border border-slate-200 bg-white text-[13px]"
      >
        <div role="rowgroup" className="sticky top-0 z-10 w-full bg-slate-50 shadow-[0_1px_0_var(--color-slate-200)]" style={{ minWidth: MIN_WIDTH }}>
          {table.getHeaderGroups().map((group) => (
            <div key={group.id} role="row" style={grid}>
              {group.headers.map((header) => {
                const sorted = header.column.getIsSorted()
                return (
                  <div
                    key={header.id}
                    role="columnheader"
                    aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : 'none'}
                    className="px-2 py-1.5"
                  >
                    <button
                      type="button"
                      className="flex w-full items-center gap-1 text-left text-xs font-semibold text-slate-600 uppercase"
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      <span aria-hidden>{sorted === 'asc' ? '▲' : sorted === 'desc' ? '▼' : ''}</span>
                    </button>
                    <input
                      aria-label={`Filter ${String(header.column.columnDef.header)}`}
                      className="mt-1 w-full rounded-chip border border-slate-200 bg-white px-1.5 py-0.5 text-xs font-normal"
                      value={(header.column.getFilterValue() as string | undefined) ?? ''}
                      onChange={(event) => header.column.setFilterValue(event.target.value || undefined)}
                    />
                  </div>
                )
              })}
            </div>
          ))}
        </div>
        <div role="rowgroup" className="relative w-full" style={{ minWidth: MIN_WIDTH, height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((item) => {
            const row = tableRows[item.index]
            const changed = changedKeys.has(row.original.row_key)
            return (
              <div
                key={row.id}
                role="row"
                data-testid="batch-row"
                data-row-key={row.original.row_key}
                aria-rowindex={item.index + 1}
                className={`absolute left-0 w-full items-center border-b border-slate-100 hover:bg-slate-50 ${changed ? 'row-changed' : ''}`}
                style={{ ...grid, height: ROW_HEIGHT, transform: `translateY(${item.start}px)` }}
              >
                {row.getVisibleCells().map((cell) => (
                  <div key={cell.id} role="cell" className="truncate px-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
        {tableRows.length === 0 && (
          <p className="p-6 text-center text-slate-500">No batches match these filters.</p>
        )}
      </div>
    </div>
  )
}
