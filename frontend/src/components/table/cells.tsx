import type { Row } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { flagChips } from '../../lib/flags'
import { formatDate, formatShortDate } from '../../lib/format'

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

export function MaterialCell({ row }: { row: Row }) {
  return (
    <div className="flex min-w-0 flex-col justify-center leading-tight">
      <div className="truncate">
        <span className="font-medium">{row.material_no}</span>{' '}
        <span className="text-slate-500">{row.material_desc}</span>
      </div>
      <div className="flex gap-1 empty:hidden">
        <TagChips flags={row.flags} />
      </div>
    </div>
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

/** The system date is struck through when a human override replaces it (05 principle 2). */
export function SystemNeedBy({ row }: { row: Row }) {
  const overridden = row.adjusted_need_by_date !== null
  return (
    <span className={overridden ? 'text-slate-400 line-through' : ''} data-testid="system-need-by">
      {formatShortDate(row.system_need_by_locked)}
    </span>
  )
}

interface AdjustedProps {
  row: Row
  canEdit: boolean
  onEdit?: (rowKey: string) => void
}

/**
 * Overridden need-by: italic with a pencil that is always shown. Otherwise the pencil appears on row hover.
 * It is disabled for read-only roles; F11 wires the modal.
 */
export function AdjustedNeedBy({ row, canEdit, onEdit }: AdjustedProps) {
  const overridden = row.adjusted_need_by_date !== null
  return (
    <span className="inline-flex items-center gap-1">
      {overridden ? (
        <span className="italic" data-testid="adjusted-need-by" title={formatDate(row.adjusted_need_by_date)}>
          {formatShortDate(row.adjusted_need_by_date)}
        </span>
      ) : (
        <span className="text-slate-400">–</span>
      )}
      <button
        type="button"
        aria-label="Edit need-by"
        disabled={!canEdit}
        title={canEdit ? 'Edit need-by' : 'Read-only role'}
        className={`rounded-chip px-1 text-slate-500 focus-visible:opacity-100 enabled:hover:bg-slate-100 enabled:hover:text-indigo-600 disabled:cursor-not-allowed ${
          overridden ? '' : 'opacity-0 group-hover:opacity-100'
        }`}
        onClick={(event) => {
          event.stopPropagation() // the row click opens the drawer; the pencil opens the editor
          onEdit?.(row.row_key)
        }}
      >
        ✎
      </button>
    </span>
  )
}

const RAG = {
  red: 'bg-red-50 text-red-700',
  amber: 'bg-amber-50 text-amber-700',
  green: 'bg-emerald-50 text-emerald-700',
}

export function RagCell({ row }: { row: Row }) {
  const rag = row.plan.rag as keyof typeof RAG | null
  if (!rag || !row.plan.expected_completion) return <span className="text-slate-400">–</span>
  const remaining = row.plan.days_remaining
  return (
    <span className={`rounded-chip px-2 py-0.5 ${RAG[rag]}`} data-testid="rag-cell" data-rag={rag}>
      {formatShortDate(row.plan.expected_completion)}
      {remaining !== null && ` · ${remaining < 0 ? `${-remaining} d late` : `${remaining} d`}`}
    </span>
  )
}

export function StatusCell({ row }: { row: Row }) {
  const status = row.manual_status as { rag?: string; team?: string } | null
  if (!status?.rag) return <span className="text-slate-400">–</span>
  const rag = status.rag as keyof typeof RAG
  return (
    <span className={`rounded-chip px-2 py-0.5 italic ${RAG[rag] ?? ''}`} title={status.team ?? ''}>
      ✎ {status.rag}
    </span>
  )
}

export function LocationCell({ row }: { row: Row }) {
  if (!row.storage_location) return <span className="text-slate-400">–</span>
  return (
    <span>
      {row.storage_location} <span className="text-slate-500">{row.location_type === '3pl' ? '3PL' : 'Onsite'}</span>
    </span>
  )
}

/** The star at the start of a row (F16-FR-04). A click bookmarks without opening the drawer. */
export function BookmarkStar({ rowKey, on, onToggle }: { rowKey: string; on: boolean; onToggle: (rowKey: string, on: boolean) => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
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
