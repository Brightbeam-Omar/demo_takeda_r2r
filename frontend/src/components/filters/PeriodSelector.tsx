import { useEffect, useRef, useState } from 'react'
import { formatDate } from '../../lib/format'
import type { Filters } from '../../state/url-filters'
import { RangeCalendar } from './RangeCalendar'

export const PERIODS: { value: string; label: string }[] = [
  { value: 'all', label: 'All dates' },
  { value: 'this_week', label: 'This week' },
  { value: 'last_week', label: 'Last week' },
  { value: 'next_week', label: 'Next week' },
  { value: 'this_month', label: 'This month' },
  { value: 'custom', label: 'Custom range…' },
]

interface Props {
  filters: Filters
  today: string
  onChange: (patch: Partial<Filters>) => void
}

export function periodLabel(filters: Filters): string {
  if (filters.period === 'custom' && filters.from && filters.to) {
    return `${formatDate(filters.from)} – ${formatDate(filters.to)}`
  }
  return PERIODS.find((period) => period.value === filters.period)?.label ?? 'All dates'
}

/** F10-FR-05. The period applies to the whole page (flow strip, alerts, table). */
export function PeriodSelector({ filters, today, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [custom, setCustom] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const choose = (value: string) => {
    if (value === 'custom') {
      setCustom(true)
      return
    }
    onChange({ period: value, from: null, to: null })
    setOpen(false)
  }

  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        aria-label="Period"
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400"
        onClick={() => {
          setOpen(!open)
          setCustom(false)
        }}
      >
        {periodLabel(filters)} ▾
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-1 rounded-card border border-slate-200 bg-white shadow-lg">
          {custom ? (
            <RangeCalendar
              start={filters.from}
              end={filters.to}
              anchor={today}
              onApply={(from, to) => {
                onChange({ period: 'custom', from, to })
                setOpen(false)
              }}
            />
          ) : (
            <ul className="w-44 p-1">
              {PERIODS.map((period) => (
                <li key={period.value}>
                  <button
                    type="button"
                    role="menuitemradio"
                    aria-checked={filters.period === period.value}
                    className={`w-full rounded-chip px-3 py-1.5 text-left hover:bg-slate-50 ${filters.period === period.value ? 'font-semibold text-indigo-700' : ''}`}
                    onClick={() => choose(period.value)}
                  >
                    {period.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
