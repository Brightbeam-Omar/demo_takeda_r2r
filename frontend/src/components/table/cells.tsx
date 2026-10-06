import type { Row } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { flagChips } from '../../lib/flags'

const CHIP_TONE = {
  neutral: 'bg-slate-100 text-slate-600',
  amber: 'bg-amber-50 text-amber-700',
  red: 'bg-red-50 text-red-700',
}

export function TagChips({ flags }: { flags: Row['flags'] }) {
  const terms = useTerms()
  const values = flags as unknown as Record<string, boolean>
  const shown = flagChips(terms).filter((chip) => chip.keys.some((key) => values[key]))
  return (
    <>
      {shown.map((chip) => (
        <span key={chip.label} className={`rounded-chip px-1.5 py-0.5 text-xs font-semibold ${CHIP_TONE[chip.tone]}`}>
          {chip.label}
        </span>
      ))}
    </>
  )
}

const LIGHT = {
  red: 'bg-red-600',
  amber: 'bg-amber-500',
  green: 'bg-emerald-600',
  grey: 'bg-slate-300',
}

/** A coloured dot with its meaning as text for assistive technology. */
export function Light({ colour, what }: { colour: string | null; what: string }) {
  const key = (colour ?? 'grey') as keyof typeof LIGHT
  return (
    <span className="inline-flex items-center gap-1.5" role="img" aria-label={`${what}: ${colour ?? 'none recorded'}`}>
      <span className={`h-2.5 w-2.5 rounded-full ${LIGHT[key] ?? LIGHT.grey}`} />
    </span>
  )
}

export function StageChip({ label, index }: { label: string; index: number }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: `var(--color-stage-${(index % 8) + 1})` }}
      />
      {label}
    </span>
  )
}

/** The star at the start of a row (F16-FR-04). A click bookmarks without opening the drawer. */
export function BookmarkStar({ rowKey, on, onToggle }: { rowKey: string; on: boolean; onToggle: (rowKey: string, on: boolean) => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      tabIndex={-1}
      aria-label={`${on ? 'Remove bookmark from' : 'Bookmark'} ${rowKey}`}
      className={`rounded-chip px-1 text-base leading-none ${on ? 'text-amber-500' : 'text-slate-300 hover:text-amber-400'}`}
      onClick={(event) => {
        event.stopPropagation()
        onToggle(rowKey, !on)
      }}
      onKeyDown={(event) => event.stopPropagation()}
    >
      {on ? '★' : '☆'}
    </button>
  )
}
