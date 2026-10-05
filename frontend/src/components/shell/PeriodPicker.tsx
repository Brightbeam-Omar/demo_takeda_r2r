import * as Popover from '@radix-ui/react-popover'
import { useState } from 'react'
import { addMonths, monthGrid } from '../../lib/calendar'
import { formatDate } from '../../lib/format'
import { QUICK_SELECT } from '../../lib/periods'
import type { Filters } from '../../state/url-filters'
import { CalendarIcon } from '../common/icons'

const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]
const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

interface Props {
  filters: Pick<Filters, 'period' | 'from' | 'to'>
  /** The demo date, ISO. The calendar opens on its month and rings it. */
  today: string
  onChange: (patch: Partial<Filters>) => void
}

export function periodLabel(filters: Pick<Filters, 'period' | 'from' | 'to'>): string {
  if (filters.period === 'custom' && filters.from && filters.to) {
    return `${formatDate(filters.from)} – ${formatDate(filters.to)}`
  }
  return QUICK_SELECT.find((option) => option.value === filters.period)?.label ?? 'All Dates'
}

/** F15-FR-04. Quick Select applies at once; a custom range is two clicks (first date, last date) then Apply. */
export function PeriodPicker({ filters, today, onChange }: Props) {
  const [open, setOpen] = useState(false)
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          data-testid="period-button"
          aria-label="Period"
          className="flex items-center gap-1.5 rounded-pill border border-hairline bg-white px-3 py-1.5 text-sm font-medium hover:border-ink-3"
        >
          <CalendarIcon />
          {periodLabel(filters)} ▾
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={6}
          data-testid="period-popover"
          className="z-40 flex rounded-card border border-hairline bg-white shadow-lg"
        >
          <QuickSelect
            active={filters.period}
            onPick={(period) => {
              onChange({ period, from: null, to: null })
              setOpen(false)
            }}
          />
          {open && (
            <RangeCalendar
              key={today}
              start={filters.period === 'custom' ? filters.from : null}
              end={filters.period === 'custom' ? filters.to : null}
              today={today}
              onApply={(from, to) => {
                onChange({ period: 'custom', from, to })
                setOpen(false)
              }}
            />
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}

function QuickSelect({ active, onPick }: { active: string; onPick: (period: string) => void }) {
  return (
    <div className="w-40 border-r border-hairline p-2">
      <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-2">Quick Select</div>
      <ul>
        {QUICK_SELECT.map((option) => (
          <li key={option.value}>
            <button
              type="button"
              aria-pressed={active === option.value}
              className={`w-full rounded-chip px-2 py-1.5 text-left text-sm ${active === option.value ? 'bg-accent-tint font-semibold text-accent' : 'hover:bg-panel'}`}
              onClick={() => onPick(option.value)}
            >
              {option.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

interface CalendarProps {
  start: string | null
  end: string | null
  today: string
  onApply: (from: string, to: string) => void
}

/** Two months side by side. The first click sets the first date, the second the last date. */
function RangeCalendar({ start, end, today, onApply }: CalendarProps) {
  const [year, month] = today.split('-').map(Number)
  const [view, setView] = useState({ year, month: month - 1 })
  const [from, setFrom] = useState(start)
  const [to, setTo] = useState(end)

  const pick = (day: string) => {
    if (!from || to) {
      setFrom(day)
      setTo(null)
    } else if (day < from) {
      setFrom(day)
    } else {
      setTo(day)
    }
  }
  const inRange = (day: string) => from !== null && to !== null && day >= from && day <= to
  const hint = !from ? 'Click a date to start' : !to ? 'Click an end date' : `${formatDate(from)} – ${formatDate(to)}`

  return (
    <div className="w-[34rem] p-3" data-testid="range-calendar">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          aria-label="Previous month"
          className="rounded-chip px-2 hover:bg-panel"
          onClick={() => setView(addMonths(view.year, view.month, -1))}
        >
          ‹
        </button>
        <button
          type="button"
          aria-label="Next month"
          className="rounded-chip px-2 hover:bg-panel"
          onClick={() => setView(addMonths(view.year, view.month, 1))}
        >
          ›
        </button>
      </div>
      <div className="flex gap-4">
        {[view, addMonths(view.year, view.month, 1)].map((shown) => (
          <div key={`${shown.year}-${shown.month}`} className="flex-1">
            <div className="mb-1 text-center font-medium">
              {MONTH_NAMES[shown.month]} {shown.year}
            </div>
            <div className="grid grid-cols-7 text-center text-xs text-ink-2">
              {WEEKDAYS.map((weekday) => (
                <span key={weekday}>{weekday}</span>
              ))}
            </div>
            <div className="grid grid-cols-7 text-center">
              {monthGrid(shown.year, shown.month)
                .flat()
                .map((day, index) =>
                  day ? (
                    <button
                      key={day}
                      type="button"
                      aria-label={formatDate(day)}
                      aria-pressed={day === from || day === to}
                      className={`h-8 text-sm ${day === from || day === to ? 'rounded-chip bg-accent text-white' : inRange(day) ? 'bg-accent-tint' : 'hover:bg-panel'} ${day === today ? 'ring-1 ring-inset ring-accent' : ''}`}
                      onClick={() => pick(day)}
                    >
                      {Number(day.slice(8))}
                    </button>
                  ) : (
                    <span key={`blank-${index}`} />
                  ),
                )}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between text-sm text-ink-2">
        <span data-testid="period-hint">{hint}</span>
        <button
          type="button"
          disabled={!from || !to}
          className="rounded-pill bg-accent px-4 py-1 text-white disabled:opacity-40"
          onClick={() => from && to && onApply(from, to)}
        >
          Apply
        </button>
      </div>
    </div>
  )
}
