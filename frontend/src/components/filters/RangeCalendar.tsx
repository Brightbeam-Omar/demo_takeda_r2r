import { useState } from 'react'
import { addMonths, monthGrid } from '../../lib/calendar'
import { formatDate } from '../../lib/format'

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

interface Props {
  start: string | null
  end: string | null
  /** The month shown on the left, as an ISO date (usually the demo "today"). */
  anchor: string
  onApply: (from: string, to: string) => void
}

/** Two months side by side. Click a first day, then a last day, then Apply. */
export function RangeCalendar({ start, end, anchor, onApply }: Props) {
  const [year, month] = anchor.split('-').map(Number)
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

  const months = [view, addMonths(view.year, view.month, 1)]
  return (
    <div className="w-[34rem] p-3" data-testid="range-calendar">
      <div className="mb-2 flex items-center justify-between">
        <button type="button" aria-label="Previous month" className="rounded-chip px-2 hover:bg-slate-100" onClick={() => setView(addMonths(view.year, view.month, -1))}>
          ‹
        </button>
        <button type="button" aria-label="Next month" className="rounded-chip px-2 hover:bg-slate-100" onClick={() => setView(addMonths(view.year, view.month, 1))}>
          ›
        </button>
      </div>
      <div className="flex gap-4">
        {months.map((shown) => (
          <div key={`${shown.year}-${shown.month}`} className="flex-1">
            <div className="mb-1 text-center font-medium">
              {MONTH_NAMES[shown.month]} {shown.year}
            </div>
            <div className="grid grid-cols-7 text-center text-xs text-slate-500">
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
                      className={`h-8 text-sm ${day === from || day === to ? 'rounded-chip bg-indigo-600 text-white' : inRange(day) ? 'bg-indigo-50' : 'hover:bg-slate-100'}`}
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
      <div className="mt-2 flex items-center justify-between text-sm text-slate-600">
        <span>{from ? `${formatDate(from)} – ${to ? formatDate(to) : 'pick an end date'}` : 'Pick a start date'}</span>
        <button
          type="button"
          disabled={!from || !to}
          className="rounded-chip bg-indigo-600 px-3 py-1 text-white disabled:opacity-40"
          onClick={() => from && to && onApply(from, to)}
        >
          Apply
        </button>
      </div>
    </div>
  )
}
