import { useEffect, useRef, useState } from 'react'
import type { Column } from './types'

interface Props<T> {
  columns: Column<T>[]
  visible: ReadonlySet<string>
  onToggle: (id: string) => void
  onReset: () => void
}

/** The `Columns` button and its checklist of every column, with `Reset` at the top (F18-FR-02). */
export function ColumnsPanel<T>({ columns, visible, onToggle, onReset }: Props<T>) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-haspopup="true"
        aria-expanded={open}
        className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400"
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => event.key === 'Escape' && setOpen(false)}
      >
        ▥ Columns
      </button>
      {open && (
        <div role="group" aria-label="Columns" className="absolute left-0 z-30 mt-1 max-h-96 w-60 overflow-auto rounded-card border border-hairline bg-white p-2 shadow-lg">
          <button type="button" className="mb-1 text-sm text-accent underline" onClick={onReset}>
            Reset
          </button>
          {columns.map((column) => (
            <label key={column.id} className="flex cursor-pointer items-center gap-2 px-1 py-0.5 text-sm hover:bg-panel">
              <input type="checkbox" checked={visible.has(column.id)} onChange={() => onToggle(column.id)} />
              {column.header}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
