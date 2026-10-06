import {
  createColumnHelper,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnFiltersState,
  type PaginationState,
  type SortingState,
} from '@tanstack/react-table'
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { saveBlob } from '../../lib/download'
import { highlight } from '../../lib/highlight'
import { Pagination } from './Pagination'
import { Toolbar } from './Toolbar'
import { toCsv, type CellContext, type Column } from './types'

export type { CellContext, Column } from './types'

const PAGE_SIZES = [25, 50, 100]
const STORAGE_PREFIX = 'r2r.columns.'

interface Props<T> {
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string
  /** File name for the exports (`-page.csv` / `-filtered.csv` are added). */
  exportName: string
  empty?: string
  /** `['lot', 'lots']`: the unit in `1–50 of 482 lots`. */
  unit?: [string, string]
  /** Text after the count, e.g. ` (91 batches)`. */
  countSuffix?: (rows: T[]) => string
  pageSizes?: number[]
  defaultPageSize?: number
  /** Persist the column choice in `sessionStorage` under this key (F18-FR-02). */
  columnsKey?: string
  /** Controlled search text (the Overview keeps it in the URL). */
  search?: { value: string; onChange: (value: string) => void }
  /** Buttons placed after Export in both toolbars. */
  toolbarExtra?: ReactNode
  /** The first column stays put while the rest scroll sideways. */
  stickyFirst?: boolean
  /** A filter box under each header (F18-FR-01). */
  headerFilters?: boolean
  rowTestId?: string
  rowClassName?: (row: T) => string
  /** A colour for the 3 px bar on the row's left edge. */
  rowAccent?: (row: T) => string | undefined
  onRowOpen?: (row: T) => void
  /** A letter pressed while the table has focus, with the row in focus (`b` bookmarks). */
  onRowKey?: (key: string, row: T) => void
  keyboardHint?: string
  ariaLabel?: string
}

const text = (value: unknown) => String(value ?? '')

function loadVisible<T>(columns: Column<T>[], key: string | undefined): Set<string> {
  const fallback = new Set(columns.filter((column) => !column.defaultHidden).map((column) => column.id))
  if (!key) return fallback
  try {
    const stored = JSON.parse(sessionStorage.getItem(STORAGE_PREFIX + key) ?? 'null') as unknown
    if (Array.isArray(stored)) {
      const known = new Set(columns.map((column) => column.id))
      const kept = stored.filter((id): id is string => typeof id === 'string' && known.has(id))
      if (kept.length > 0) return new Set(kept)
    }
  } catch {
    // unreadable storage: use the defaults
  }
  return fallback
}

/**
 * The shared list table (F18-FR-01): sortable headers with a filter box beneath each, search over every
 * visible column with highlighting, a Columns panel, client-side pagination, exports of what is on screen, a
 * toolbar above and below, and keyboard navigation of the rows. The Overview and the list windows use it.
 */
export function DataTable<T>({
  rows,
  columns,
  rowKey,
  exportName,
  empty = 'Nothing to show.',
  unit = ['row', 'rows'],
  countSuffix,
  pageSizes = PAGE_SIZES,
  defaultPageSize = 50,
  columnsKey,
  search,
  toolbarExtra,
  stickyFirst = true,
  headerFilters = true,
  rowTestId = 'window-row',
  rowClassName,
  rowAccent,
  onRowOpen,
  onRowKey,
  keyboardHint,
  ariaLabel = 'Table',
}: Props<T>) {
  // Unsorted = the order the rows arrive in (the server's exceptions-first order for the Overview).
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [localSearch, setLocalSearch] = useState('')
  const q = search ? search.value : localSearch
  const setQ = search ? search.onChange : setLocalSearch
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: defaultPageSize })
  const [visible, setVisible] = useState<Set<string>>(() => loadVisible(columns, columnsKey))
  const [active, setActive] = useState<number | null>(null)
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (columnsKey) sessionStorage.setItem(STORAGE_PREFIX + columnsKey, JSON.stringify([...visible]))
  }, [visible, columnsKey])

  const byId = useMemo(() => new Map(columns.map((column) => [column.id, column])), [columns])
  const visibleColumns = useMemo(() => columns.filter((column) => visible.has(column.id)), [columns, visible])

  // Search every visible column's displayed text (F18-FR-05).
  const searched = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return rows
    return rows.filter((row) => visibleColumns.some((column) => column.text(row).toLowerCase().includes(needle)))
  }, [rows, q, visibleColumns])

  const defs = useMemo(() => {
    const helper = createColumnHelper<T>()
    return columns.map((column) =>
      helper.accessor((row) => (column.sortValue ? column.sortValue(row) : column.text(row)), {
        id: column.id,
        header: column.header,
        sortUndefined: 'last',
        filterFn: (row, _id, value: string) => column.text(row.original).toLowerCase().includes(String(value).toLowerCase()),
      }),
    )
  }, [columns])

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table v8 hands back unmemoised functions; nothing here depends on their identity
  const table = useReactTable({
    data: searched,
    columns: defs,
    state: {
      sorting,
      columnFilters,
      pagination,
      columnVisibility: Object.fromEntries(columns.map((column) => [column.id, visible.has(column.id)])),
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    autoResetPageIndex: true,
  })

  const filtered = table.getPrePaginationRowModel().rows
  const pageRows = table.getRowModel().rows
  const matches = filtered.length
  const { pageIndex, pageSize } = table.getState().pagination
  const first = matches === 0 ? 0 : pageIndex * pageSize + 1
  const last = Math.min(matches, (pageIndex + 1) * pageSize)
  const [one, many] = unit
  const count =
    matches === 0 ? (
      'No results'
    ) : (
      <>
        {first}–{last} of {matches} {matches === 1 ? one : many}
        {countSuffix?.(filtered.map((row) => row.original)) ?? ''}
      </>
    )

  const context: CellContext = { q, hl: (value) => highlight(value, q) }
  const download = (subset: T[], suffix: string) =>
    saveBlob(new Blob([toCsv(visibleColumns, subset)], { type: 'text/csv' }), `${exportName}-${suffix}.csv`)
  const reset = () => {
    setSorting([])
    setColumnFilters([])
    setPagination((state) => ({ ...state, pageIndex: 0 }))
  }
  const toggleColumn = (id: string) =>
    setVisible((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next.size === 0 ? current : next
    })
  const resetColumns = () => setVisible(new Set(columns.filter((column) => !column.defaultHidden).map((column) => column.id)))

  const toolbar = (position: 'top' | 'bottom') => (
    <Toolbar
      position={position}
      columns={columns}
      visible={visible}
      onToggleColumn={toggleColumn}
      onResetColumns={resetColumns}
      search={q}
      onSearch={setQ}
      count={count}
      pageRows={pageRows.length}
      filteredRows={matches}
      onExportPage={() => download(pageRows.map((row) => row.original), 'page')}
      onExportFiltered={() => download(filtered.map((row) => row.original), 'filtered')}
      onReset={reset}
      extra={toolbarExtra}
    />
  )

  const focusRow = (index: number) => {
    setActive(index)
    scroller.current?.querySelector(`[data-index="${index}"]`)?.scrollIntoView({ block: 'nearest' })
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    // Only while the table itself has focus: typing in a filter box or pressing a button inside a row is left alone.
    if (event.target !== event.currentTarget || pageRows.length === 0) return
    const at = active ?? 0
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusRow(Math.min(pageRows.length - 1, at + 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusRow(Math.max(0, at - 1))
    } else if (event.key === 'Enter') {
      const row = pageRows[at]
      if (row) onRowOpen?.(row.original)
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const row = pageRows[at]
      if (row) onRowKey?.(event.key.toLowerCase(), row.original)
    }
  }

  const sticky = 'sticky left-0 z-[1] bg-inherit'
  return (
    <div className="space-y-2">
      {toolbar('top')}
      <div
        ref={scroller}
        role="grid"
        tabIndex={0}
        aria-label={ariaLabel}
        aria-rowcount={matches}
        aria-activedescendant={active !== null && pageRows[active] ? `row-${rowKey(pageRows[active].original)}` : undefined}
        className="max-h-[640px] overflow-auto rounded-card border border-slate-200 bg-white text-[13px] focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
        onKeyDown={onKeyDown}
        onFocus={(event) => {
          if (event.target === event.currentTarget && active === null) setActive(0)
        }}
      >
        <table className="w-max min-w-full border-collapse text-left whitespace-nowrap">
          <thead className="sticky top-0 z-[2] bg-slate-50 shadow-[0_1px_0_var(--color-slate-200)]">
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header, index) => {
                  const sorted = header.column.getIsSorted()
                  const label = String(header.column.columnDef.header)
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : 'none'}
                      className={`px-2 py-1.5 align-top ${stickyFirst && index === 0 ? `${sticky} bg-slate-50` : ''}`}
                    >
                      <button
                        type="button"
                        className="flex items-center gap-1 text-[11px] font-semibold tracking-wider text-slate-600 uppercase"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {label}
                        <span aria-hidden className="w-2.5">
                          {sorted === 'asc' ? '▲' : sorted === 'desc' ? '▼' : ''}
                        </span>
                      </button>
                      {headerFilters && (
                        <input
                          aria-label={`Filter ${label}`}
                          placeholder="Filter"
                          className="mt-1 w-full min-w-16 rounded-chip border border-slate-300 bg-white px-1.5 py-0.5 text-xs font-normal"
                          value={(header.column.getFilterValue() as string | undefined) ?? ''}
                          onChange={(event) => header.column.setFilterValue(event.target.value || undefined)}
                        />
                      )}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {pageRows.map((row, index) => {
              const accent = rowAccent?.(row.original)
              return (
                <tr
                  key={rowKey(row.original)}
                  id={`row-${rowKey(row.original)}`}
                  data-testid={rowTestId}
                  data-row-key={rowKey(row.original)}
                  data-index={index}
                  data-active={active === index ? 'true' : undefined}
                  onClick={() => {
                    setActive(index)
                    onRowOpen?.(row.original)
                  }}
                  className={`group border-t border-slate-100 bg-white align-middle hover:bg-slate-50 ${onRowOpen ? 'cursor-pointer' : ''} ${
                    active === index ? 'outline-2 -outline-offset-2 outline-accent' : ''
                  } ${rowClassName?.(row.original) ?? ''}`}
                >
                  {row.getVisibleCells().map((cell, cellIndex) => {
                    const column = byId.get(cell.column.id)
                    return (
                      <td
                        key={cell.id}
                        className={`px-2 py-2 ${stickyFirst && cellIndex === 0 ? sticky : ''}`}
                        style={accent && cellIndex === 0 ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}
                      >
                        {column ? column.cell(row.original, context) : text(cell.getValue())}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
        {matches === 0 && <p className="p-6 text-center text-slate-500">{rows.length === 0 ? empty : 'No results'}</p>}
      </div>
      {keyboardHint && (
        <p className="text-xs text-slate-500" data-testid="keyboard-hint">
          {keyboardHint}
        </p>
      )}
      {toolbar('bottom')}
      <Pagination table={table} pageSizes={pageSizes} />
    </div>
  )
}

