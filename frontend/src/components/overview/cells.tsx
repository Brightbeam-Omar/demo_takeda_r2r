import type { ReactNode } from 'react'
import type { Row } from '../../api/queries'
import type { Terms } from '../../hooks/useTerms'
import { formatDate } from '../../lib/format'
import { slaDeadline, statusOf, expectedText } from '../../lib/status'
import { tagRow, type Tag } from '../../lib/tags'
import { ExplainPopover } from '../explain/ExplainPopover'

type Hl = (text: string) => ReactNode

/** The tags that apply to a row, in the tag row's order (F18-FR-03a). */
export function rowTags(row: Row, terms: Terms): Tag[] {
  const flags = row.flags as unknown as Record<string, boolean>
  return tagRow(terms).filter((tag) => tag.keys.some((key) => flags[key]))
}

/** A chip in the tag's own colours, without the hover effect of the tag-row button. */
const chipClass = (tag: Tag) => tag.off.split(' ').filter((name) => !name.startsWith('hover:')).join(' ')

export function TagChips({ row, terms }: { row: Row; terms: Terms }) {
  return (
    <>
      {rowTags(row, terms).map((tag) => (
        <span key={tag.id} className={`rounded-chip border px-1.5 py-px text-[10px] font-semibold tracking-wide ${chipClass(tag)}`}>
          {tag.label}
        </span>
      ))}
    </>
  )
}

interface MaterialProps {
  row: Row
  terms: Terms
  hl: Hl
  star: ReactNode
  actions: ReactNode
}

/** Star, bold code, description, supplier batch, tag chips and the `⋯` menu in one cell (F18-FR-03a). */
export function MaterialCell({ row, terms, hl, star, actions }: MaterialProps) {
  return (
    <div className="flex items-start gap-1">
      {star}
      <div className="flex flex-col leading-tight">
        <span className="font-semibold">{hl(row.material_no)}</span>
        <span className="text-slate-700">{hl(row.material_desc ?? '')}</span>
        <span className="text-xs text-slate-500">{hl(row.supplier_batch ?? '')}</span>
        <span className="flex gap-1 empty:hidden">
          <TagChips row={row} terms={terms} />
        </span>
      </div>
      {actions}
    </div>
  )
}

const DOT = { red: 'bg-red-600', amber: 'bg-amber-500', green: 'bg-emerald-600', grey: 'bg-slate-300' }

/** An 8 px status dot (F18-FR-03c) with its meaning as text for assistive technology. */
export function Dot({ colour, what }: { colour: string | null; what: string }) {
  const key = (colour ?? 'grey') as keyof typeof DOT
  return (
    <span role="img" aria-label={`${what}: ${colour ?? 'none recorded'}`} className={`inline-block h-2 w-2 rounded-full ${DOT[key] ?? DOT.grey}`} />
  )
}

/** A pill in the stage's colour: light tint, strong text (05 v2 section 2). */
export function StageBadge({ row, index }: { row: Row; index: number }) {
  const colour = `var(--color-stage-${(index % 8) + 1})`
  const samples = (row as unknown as { sample_count?: number }).sample_count
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className="rounded-full px-2 py-0.5 text-xs font-semibold"
        style={{ backgroundColor: `color-mix(in srgb, ${colour} 20%, white)`, color: `color-mix(in srgb, ${colour} 35%, black)` }}
      >
        {row.stage_label}
      </span>
      {samples !== undefined && <span className="rounded-full bg-slate-200 px-1.5 text-[10px] font-semibold text-slate-700">{samples}</span>}
      <ExplainPopover
        what="stage"
        path={`/rows/${encodeURIComponent(row.row_key)}/explain`}
        params={new URLSearchParams({ field: 'stage' })}
        className="opacity-0 group-hover:opacity-100"
      />
    </span>
  )
}

export function SystemNeedBy({ row }: { row: Row }) {
  const overridden = row.adjusted_need_by_date !== null
  return (
    <span className={overridden ? 'text-slate-400 line-through' : ''} data-testid="system-need-by">
      {row.system_need_by_locked ? formatDate(row.system_need_by_locked) : '—'}
    </span>
  )
}

interface AdjustedProps {
  row: Row
  canEdit: boolean
  onEdit?: (rowKey: string) => void
}

/** The adjusted date with a pencil, or `+ set date ✎` when there is none; both open the need-by modal (F18-FR-03e). */
export function AdjustedDate({ row, canEdit, onEdit }: AdjustedProps) {
  const overridden = row.adjusted_need_by_date !== null
  return (
    <button
      type="button"
      aria-label="Edit need-by"
      disabled={!canEdit}
      title={canEdit ? 'Edit need-by' : 'Read-only role'}
      tabIndex={-1}
      className={`rounded-chip px-1 text-left enabled:hover:bg-slate-100 enabled:hover:text-accent disabled:cursor-not-allowed ${overridden ? 'italic' : 'text-slate-500'}`}
      onClick={(event) => {
        event.stopPropagation() // the row click opens the drawer; this opens the editor
        onEdit?.(row.row_key)
      }}
    >
      {overridden ? (
        <span data-testid="adjusted-need-by" className="italic">
          {formatDate(row.adjusted_need_by_date)} ✎
        </span>
      ) : (
        <span>+ set date ✎</span>
      )}
    </button>
  )
}

const RAG_DOT = { red: 'bg-red-600', amber: 'bg-amber-500', green: 'bg-emerald-600' }

/** The current stage's `must_complete_by` with a RAG dot (F18-FR-03f). */
export function SlaDeadline({ row }: { row: Row }) {
  const date = slaDeadline(row)
  if (!date) return <span className="text-slate-400">—</span>
  const rag = row.plan.rag as keyof typeof RAG_DOT | null
  return (
    <span className="inline-flex items-center gap-1.5" data-testid="sla-deadline">
      {rag && <span aria-hidden className={`h-2 w-2 rounded-full ${RAG_DOT[rag]}`} />}
      {formatDate(date)}
    </span>
  )
}

const STATUS = {
  late: 'text-red-700 font-semibold',
  due: 'text-amber-700 font-semibold',
  ok: 'text-emerald-700 font-semibold',
  none: 'text-slate-400',
}

/** `LATE +12d` / `DUE IN 2d` / `ON TRACK` / `—` (F18-FR-03h), with the F19 status-log comment once it is published. */
export function StatusCell({ row, hl }: { row: Row; hl: Hl }) {
  const status = statusOf(row)
  const latest = (row as unknown as { latest_status?: string | null }).latest_status
  return (
    <span className="flex flex-col leading-tight">
      <span className={STATUS[status.kind]} data-testid="status-cell" data-status={status.kind}>
        {hl(status.text)}
      </span>
      {latest ? <span className="text-xs text-slate-500">{latest}</span> : null}
    </span>
  )
}

/** The date, or `17 Aug 2026 (56d over)` with the whole cell red when overdue (F18-FR-03i). */
export function ExpectedCell({ row, hl }: { row: Row; hl: Hl }) {
  const text = expectedText(row)
  return (
    <span className="inline-flex items-center gap-1">
      <span className={row.plan.late ? 'font-semibold text-red-700' : ''} data-testid="expected-cell" data-late={row.plan.late ? 'true' : undefined}>
        {hl(text)}
      </span>
      {row.plan.expected_completion ? (
        <ExplainPopover
          what="expected completion"
          path={`/rows/${encodeURIComponent(row.row_key)}/explain`}
          params={new URLSearchParams({ field: 'expected_completion' })}
          className="opacity-0 group-hover:opacity-100"
        />
      ) : null}
    </span>
  )
}
