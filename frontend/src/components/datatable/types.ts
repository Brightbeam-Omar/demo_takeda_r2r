import type { ReactNode } from 'react'

/** What a cell renderer gets besides its row: the search text and the helper that marks matches in it. */
export interface CellContext {
  q: string
  hl: (text: string) => ReactNode
}

export interface Column<T> {
  id: string
  header: string
  /** What the cell shows. */
  cell: (row: T, context: CellContext) => ReactNode
  /** The cell's displayed text: used by search, the header filter, sorting (unless `sortValue`) and the CSV export. */
  text: (row: T) => string
  /** A numeric or text sort key, when the text would sort wrongly (days, dates). */
  sortValue?: (row: T) => number | string
  /** Off until the user turns it on in the Columns panel (F18-FR-02). */
  defaultHidden?: boolean
}

export const csvCell = (value: string) => (/[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value)

export function toCsv<T>(columns: Column<T>[], rows: T[]): string {
  const lines = [columns.map((column) => csvCell(column.header)).join(',')]
  for (const row of rows) lines.push(columns.map((column) => csvCell(column.text(row))).join(','))
  return `${lines.join('\n')}\n`
}
