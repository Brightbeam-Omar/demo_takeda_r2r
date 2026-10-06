import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ColumnsPanel } from './ColumnsPanel'
import type { Column } from './types'

const BUTTON = 'rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400 disabled:opacity-50'

interface Props<T> {
  columns: Column<T>[]
  visible: ReadonlySet<string>
  onToggleColumn: (id: string) => void
  onResetColumns: () => void
  search: string
  onSearch: (value: string) => void
  count: ReactNode
  pageRows: number
  filteredRows: number
  onExportPage: () => void
  onExportFiltered: () => void
  onReset: () => void
  extra?: ReactNode
  position: 'top' | 'bottom'
}

/** `[↓ Export ▾] [extras] [▥ Columns] [⌕ Search all columns…]  1–50 of 482 lots  [↺ Reset Table]` (F18-FR-01). */
export function Toolbar<T>({
  columns,
  visible,
  onToggleColumn,
  onResetColumns,
  search,
  onSearch,
  count,
  pageRows,
  filteredRows,
  onExportPage,
  onExportFiltered,
  onReset,
  extra,
  position,
}: Props<T>) {
  const [menu, setMenu] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!menu) return
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setMenu(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menu])
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid={`table-toolbar-${position}`}>
      <div ref={box} className="relative">
        <button type="button" aria-haspopup="true" aria-expanded={menu} className={BUTTON} onClick={() => setMenu(!menu)} onKeyDown={(event) => event.key === 'Escape' && setMenu(false)}>
          ↓ Export ▾
        </button>
        {menu && (
          <div role="menu" className="absolute left-0 z-30 mt-1 w-60 rounded-card border border-hairline bg-white py-1 shadow-lg">
            <button
              type="button"
              role="menuitem"
              className="block w-full px-3 py-1.5 text-left text-sm hover:bg-panel"
              onClick={() => {
                setMenu(false)
                onExportPage()
              }}
            >
              This page ({pageRows} rows)
            </button>
            <button
              type="button"
              role="menuitem"
              className="block w-full px-3 py-1.5 text-left text-sm hover:bg-panel"
              onClick={() => {
                setMenu(false)
                onExportFiltered()
              }}
            >
              All filtered results ({filteredRows} rows)
            </button>
          </div>
        )}
      </div>
      {extra}
      <ColumnsPanel columns={columns} visible={visible} onToggle={onToggleColumn} onReset={onResetColumns} />
      <div className="relative">
        <input
          type="text"
          aria-label="Search all columns"
          placeholder="⌕ Search all columns…"
          className="w-64 rounded-chip border border-slate-300 bg-white py-1.5 pr-7 pl-3 text-sm"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
        />
        {search && (
          <button type="button" aria-label="Clear search" className="absolute top-1/2 right-1.5 -translate-y-1/2 px-1 text-slate-500 hover:text-slate-800" onClick={() => onSearch('')}>
            ×
          </button>
        )}
      </div>
      <span className="text-sm text-slate-600" data-testid={position === 'top' ? 'page-summary' : undefined}>
        {count}
      </span>
      <button type="button" className={`${BUTTON} ml-auto`} onClick={onReset}>
        ↺ Reset Table
      </button>
    </div>
  )
}
