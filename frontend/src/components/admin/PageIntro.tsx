import type { ReactNode } from 'react'

/** The title block of an admin page: a subtitle, and the clock note as a tooltip (OQ-135). */
export function PageIntro({ subtitle, clockNote }: { subtitle: ReactNode; clockNote?: string }) {
  return (
    <p className="text-sm text-ink-2" data-testid="page-subtitle">
      {subtitle}
      {clockNote ? (
        <span
          tabIndex={0}
          role="note"
          aria-label={clockNote}
          title={clockNote}
          data-testid="clock-note"
          className="ml-2 cursor-help rounded-pill border border-hairline px-1.5 text-xs text-ink-2"
        >
          ⓘ
        </span>
      ) : null}
    </p>
  )
}
