import { useEffect, useRef, useState } from 'react'

export interface Option {
  value: string
  label: string
  count?: number
}

interface Props {
  label: string
  options: Option[]
  selected: string[]
  onChange: (selected: string[]) => void
  searchable?: boolean
}

/** A dropdown of checkboxes; the button shows the label and how many values are picked. */
export function MultiSelect({ label, options, selected, onChange, searchable = false }: Props) {
  const [open, setOpen] = useState(false)
  const [term, setTerm] = useState('')
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const shown = options.filter((option) => option.label.toLowerCase().includes(term.toLowerCase()))
  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])

  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`rounded-chip border px-3 py-1.5 text-sm ${selected.length > 0 ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-slate-300 bg-white text-slate-700'} hover:border-slate-400`}
        onClick={() => setOpen(!open)}
      >
        {label}
        {selected.length > 0 ? ` (${selected.length})` : ''} ▾
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-60 rounded-card border border-slate-200 bg-white p-2 shadow-lg">
          {searchable && (
            <input
              type="search"
              aria-label={`Search ${label}`}
              placeholder={`Search ${label.toLowerCase()}…`}
              className="mb-2 w-full rounded-chip border border-slate-300 px-2 py-1 text-sm"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
            />
          )}
          <ul role="listbox" aria-label={label} aria-multiselectable className="max-h-64 overflow-auto">
            {shown.map((option) => (
              <li key={option.value} role="option" aria-selected={selected.includes(option.value)}>
                <label className="flex cursor-pointer items-center gap-2 rounded-chip px-2 py-1 hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={selected.includes(option.value)}
                    onChange={() => toggle(option.value)}
                  />
                  <span className="flex-1">{option.label}</span>
                  {option.count !== undefined && <span className="text-xs text-slate-500">{option.count}</span>}
                </label>
              </li>
            ))}
            {shown.length === 0 && <li className="px-2 py-1 text-slate-500">No matches</li>}
          </ul>
        </div>
      )}
    </div>
  )
}
