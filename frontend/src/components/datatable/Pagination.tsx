import type { Table } from '@tanstack/react-table'

const BUTTON = 'rounded-chip border border-slate-300 bg-white px-2 py-0.5 text-sm hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40'

interface Props<T> {
  table: Table<T>
  pageSizes: number[]
}

/** `« ‹ Prev  Page 1 of 17  Next › »  Rows per page [50]` (F18-FR-01). */
export function Pagination<T>({ table, pageSizes }: Props<T>) {
  const { pageIndex, pageSize } = table.getState().pagination
  const pages = Math.max(1, table.getPageCount())
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
      <button type="button" aria-label="First page" className={BUTTON} disabled={!table.getCanPreviousPage()} onClick={() => table.setPageIndex(0)}>
        «
      </button>
      <button type="button" aria-label="Previous page" className={BUTTON} disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}>
        ‹ Prev
      </button>
      <span data-testid="page-of">
        Page {pageIndex + 1} of {pages}
      </span>
      <button type="button" aria-label="Next page" className={BUTTON} disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}>
        Next ›
      </button>
      <button type="button" aria-label="Last page" className={BUTTON} disabled={!table.getCanNextPage()} onClick={() => table.setPageIndex(pages - 1)}>
        »
      </button>
      <label className="flex items-center gap-1">
        Rows per page
        <select
          aria-label="Rows per page"
          className="rounded-chip border border-slate-300 bg-white px-1 py-0.5"
          value={pageSize}
          onChange={(event) => table.setPageSize(Number(event.target.value))}
        >
          {pageSizes.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}
