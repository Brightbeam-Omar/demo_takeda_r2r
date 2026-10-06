import type { ReactNode } from 'react'
import { RAG_HEX } from '../../lib/chartColours'

interface Props {
  testId: string
  title: string
  /** The big figure: `318 / 700`, `87.6%`. */
  figure: string
  /** Fill of the bar, 0 to 100. */
  fill: number
  /** Where the target marker sits on the bar, 0 to 100. */
  marker?: number
  markerLabel?: string
  rag?: string | null
  /** Counts beneath the bar. */
  counts: ReactNode
  note?: ReactNode
}

/** An Executive Summary card: big figure, a bar with a target marker, counts beneath (F20 layout). */
export function ProgressCard({ testId, title, figure, fill, marker, markerLabel, rag, counts, note }: Props) {
  const colour = RAG_HEX[rag ?? 'grey']
  return (
    <section data-testid={testId} data-rag={rag ?? undefined} className="rounded-card border border-hairline bg-white p-4">
      <h3 className="text-[11px] font-semibold tracking-wider text-ink-2 uppercase">{title}</h3>
      <div className="mt-1 text-3xl font-semibold tabular-nums" data-testid={`${testId}-figure`}>
        {figure}
      </div>
      <div className="relative mt-3 h-2.5 rounded-pill bg-panel" role="img" aria-label={`${title}: ${figure}`}>
        <div className="h-full rounded-pill" data-testid={`${testId}-fill`} style={{ width: `${fill}%`, backgroundColor: colour }} />
        {marker !== undefined && (
          <div
            data-testid={`${testId}-marker`}
            title={markerLabel}
            className="absolute -top-1 h-4.5 w-0.5 bg-ink"
            style={{ left: `${marker}%` }}
          />
        )}
      </div>
      <div className="mt-2 text-sm text-ink" data-testid={`${testId}-counts`}>
        {counts}
      </div>
      {note && <div className="mt-1 text-xs text-ink-2">{note}</div>}
    </section>
  )
}
