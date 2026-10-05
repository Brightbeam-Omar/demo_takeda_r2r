import type { ReactNode } from 'react'
import { ExplainPopover } from '../explain/ExplainPopover'

interface Props {
  testId: string
  eyebrow: string
  title: string
  count: number
  selected: boolean
  onClick: () => void
  /** The line under the count: `SLA 10 d`, a caption, … */
  detail?: ReactNode
  late?: number
  /** Green "N skip call-off" note. */
  skip?: string
  /** Colour of the 4 px top bar. */
  barColor?: string
  explain?: { what: string; params: URLSearchParams }
}

/** A selectable pipeline card (F17-FR-05): grey when off, lavender tint with an indigo outline when on. */
export function StageCard({ testId, eyebrow, title, count, selected, onClick, detail, late = 0, skip, barColor, explain }: Props) {
  return (
    <div className="relative flex min-w-[92px] flex-1">
      <button
        type="button"
        data-testid={testId}
        aria-pressed={selected}
        onClick={onClick}
        style={barColor ? { borderTopColor: barColor } : undefined}
        className={`w-full rounded-card border border-t-4 px-2.5 py-2 text-left hover:shadow ${
          selected ? 'border-accent bg-accent-tint ring-2 ring-accent' : 'border-hairline bg-panel'
        }`}
      >
        <div className="text-[11px] font-semibold tracking-wider text-ink-2 uppercase">{eyebrow}</div>
        <div className="truncate text-sm font-semibold text-ink" title={title}>
          {title}
        </div>
        <div className="text-2xl font-semibold tabular-nums">{count}</div>
        <div className="flex min-h-4 items-center justify-between gap-1.5 text-xs whitespace-nowrap">
          <span className="text-ink-2">{detail}</span>
          {late > 0 && (
            <span className="font-semibold text-rag-red" data-testid={`late-${testId.replace('flow-', '')}`}>
              {late} late
            </span>
          )}
        </div>
        {skip && (
          <div className="text-xs font-medium text-rag-green" data-testid={`skip-${testId.replace('flow-', '')}`}>
            {skip}
          </div>
        )}
      </button>
      {explain && (
        <span className="absolute top-1.5 right-1.5">
          <ExplainPopover what={explain.what} path="/explain" params={explain.params} />
        </span>
      )}
    </div>
  )
}
