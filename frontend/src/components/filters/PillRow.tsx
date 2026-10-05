import type { ReactNode } from 'react'

export interface PillOption {
  value: string
  label: string
  count?: number
}

export const pillClass = (on: boolean) =>
  `rounded-pill border px-3 py-1 text-sm ${on ? 'border-indigo-600 bg-indigo-50 font-medium text-indigo-700' : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'}`

interface Props {
  label: string
  options: PillOption[]
  selected: string[]
  onChange: (selected: string[]) => void
  /** Extra content after the pills (the campaign search and view toggle). */
  children?: ReactNode
}

/** One row of the filter panel: an "All" pill and one pill per option. Values within a row are ORed; "All" clears the row. */
export function PillRow({ label, options, selected, onChange, children }: Props) {
  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])
  return (
    <div role="group" aria-label={label} className="flex items-start gap-3">
      <span className="w-20 shrink-0 pt-1 text-sm font-semibold text-slate-500">{label}</span>
      <div className="flex flex-1 flex-wrap items-center gap-2">
        <button type="button" aria-pressed={selected.length === 0} className={pillClass(selected.length === 0)} onClick={() => onChange([])}>
          All
        </button>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected.includes(option.value)}
            className={pillClass(selected.includes(option.value))}
            onClick={() => toggle(option.value)}
          >
            {option.label}
            {option.count !== undefined && <span className="ml-1.5 text-xs text-slate-500">{option.count}</span>}
          </button>
        ))}
        {children}
      </div>
    </div>
  )
}
