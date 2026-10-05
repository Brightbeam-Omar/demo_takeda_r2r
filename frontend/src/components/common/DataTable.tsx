import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { useMemo, useState, type ReactNode } from 'react'
import { saveBlob } from '../../lib/download'

export interface Column<T> {
  id: string
  header: string
  /** What the cell shows. */
  cell: (row: T) => ReactNode
  /** Plain text for search, sort and the CSV export. */
  text: (row: T) => string
  /** A numeric sort key, when the text would sort wrongly (days, deltas). */
  sortValue?: (row: T) => number
}

interface Props<T> {
  rows: T[]
  columns: Column<T>[]
  /** File name for Export (a `.csv` is added). */
  exportName: string
  rowKey: (row: T) => string
  empty?: string
}

const PAGE_SIZES = [10, 25, 50]

const csvCell = (value: string) => (/[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value)

/** The shared list table for the Overview windows: search all columns, sort, paginate, reset, export (F16-FR-07). F18 extends it. */
export function DataTable<T>({ rows, columns, exportName, rowKey, empty = 'Nothing to show.' }: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [search, setSearch] = useState('')
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: PAGE_SIZES[0]! })

  const defs = useMemo(() => {
    const helper = createColumnHelper<T>()
    return columns.map((column) =>
      helper.accessor((row) => (column.sortValue ? column.sortValue(row) : column.text(row)), {
        id: column.id,
        header: column.header,
        cell: ({ row }) => column.cell(row.original),
      }),
    )
  }, [columns])

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table v8 hands back unmemoised functions; nothing here depends on their identity
  const table = useReactTable({
    data: rows,
    columns: defs,
    state: { sorting, globalFilter: search, pagination },
    onSortingChange: setSorting,
    onGlobalFilterChange: setSearch,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    autoResetPageIndex: true,
    // Search over what the cells show, not the sort keys.
    globalFilterFn: (row, _id, value: string) =>
      columns.some((column) => column.text(row.original).toLowerCase().includes(String(value).toLowerCase())),
  })

  const reset = () => {
    setSearch('')
    setSorting([])
    setPagination({ pageIndex: 0, pageSize: PAGE_SIZES[0]! })
  }
  const exportCsv = () => {
    const lines = [columns.map((column) => csvCell(column.header)).join(',')]
    for (const row of table.getPrePaginationRowModel().rows) {
      lines.push(columns.map((column) => csvCell(column.text(row.original))).join(','))
    }
    saveBlob(new Blob([`${lines.join('\n')}\n`], { type: 'text/csv' }), `${exportName}.csv`)
  }

  const matches = table.getPrePaginationRowModel().rows.length
  const { pageIndex, pageSize } = table.getState().pagination
  const pages = Math.max(1, table.getPageCount())
  const first = matches === 0 ? 0 : pageIndex * pageSize + 1
  const last = Math.min(matches, (pageIndex + 1) * pageSize)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400" onClick={exportCsv}>
          Export
        </button>
        <input
          type="search"
          aria-label="Search all columns"
          placeholder="Search all columns…"
          className="w-64 rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <button type="button" className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400" onClick={reset}>
          Reset Table
        </button>
      </div>
      <div className="overflow-auto rounded-card border border-slate-200">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted()
                  return (
                    <th key={header.id} scope="col" aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : 'none'} className="px-3 py-2">
                      <button type="button" className="flex items-center gap-1 uppercase" onClick={header.column.getToggleSortingHandler()}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        <span aria-hidden>{sorted === 'asc' ? '▲' : sorted === 'desc' ? '▼' : ''}</span>
                      </button>
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={rowKey(row.original)} data-testid="window-row" className="border-t border-slate-100 align-top">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {matches === 0 && <p className="p-6 text-center text-slate-500">{rows.length === 0 ? empty : 'No rows match the search.'}</p>}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
        <span data-testid="page-summary">
          {first}–{last} of {matches}
        </span>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1">
            Rows per page
            <select
              aria-label="Rows per page"
              className="rounded-chip border border-slate-300 bg-white px-1 py-0.5"
              value={pageSize}
              onChange={(event) => table.setPageSize(Number(event.target.value))}
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <button type="button" aria-label="Previous page" disabled={!table.getCanPreviousPage()} className="rounded-chip border border-slate-300 px-2 py-0.5 disabled:opacity-40" onClick={() => table.previousPage()}>
            ‹
          </button>
          <span>
            Page {pageIndex + 1} of {pages}
          </span>
          <button type="button" aria-label="Next page" disabled={!table.getCanNextPage()} className="rounded-chip border border-slate-300 px-2 py-0.5 disabled:opacity-40" onClick={() => table.nextPage()}>
            ›
          </button>
        </div>
      </div>
    </div>
  )
}
