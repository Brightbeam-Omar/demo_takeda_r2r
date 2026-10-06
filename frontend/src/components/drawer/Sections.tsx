import type { ReactNode } from 'react'
import type { RowDetail } from '../../api/queries'
import { formatDate, humanize } from '../../lib/format'
import { inboundState, sampleCounts } from '../../lib/windows'
import type { WindowName } from '../../state/batch-view'
import { ExplainPopover } from '../explain/ExplainPopover'
import { Dot } from '../overview/cells'

export function DrawerSection({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section aria-label={title} className="border-t border-slate-200 px-5 py-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  )
}

/** The `Open ↗` link of a summary section: it opens that section's window on top of the drawer (OQ-116). */
export function OpenLink({ label, win, onOpen }: { label: string; win: WindowName; onOpen: (win: WindowName) => void }) {
  return (
    <button
      type="button"
      aria-label={`Open ${label} window`}
      data-window={win}
      className="rounded-chip px-2 py-0.5 text-xs font-medium text-accent hover:bg-accent-tint"
      onClick={() => onOpen(win)}
    >
      Open ↗
    </button>
  )
}

const RAG_TEXT = { red: 'text-red-700', amber: 'text-amber-700', green: 'text-emerald-700' }

/** Quality: the deviation rating, the open deviations and the changes (opens W3). */
export function QualitySummary({ detail }: { detail: RowDetail }) {
  const open = detail.deviations.filter((d) => d.status === 'open').length
  const rating = detail.deviation_light ?? 'grey'
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]" data-testid="quality-summary">
      <span className="inline-flex items-center gap-1.5 font-medium">
        <Dot colour={rating} what="Deviations" />
        {humanize(rating)}
      </span>
      <span>
        {open} open {open === 1 ? 'deviation' : 'deviations'}
      </span>
      <span>
        {detail.changes.length} {detail.changes.length === 1 ? 'change' : 'changes'}
      </span>
    </div>
  )
}

/** Inbound: the result and the failed-check count (opens W2). */
export function InboundSummary({ detail }: { detail: RowDetail }) {
  const state = inboundState(detail.inbound_check)
  const failed = detail.inbound_check?.failed_count ?? 0
  return (
    <div className="flex flex-wrap items-center gap-x-3 text-[13px]" data-testid="inbound-summary">
      <span className="inline-flex items-center gap-1.5 font-medium">
        <Dot colour={state.colour} what="Inbound check" />
        {state.label}
      </span>
      {failed > 0 && <span className="text-red-700">Failed checks: {failed}</span>}
    </div>
  )
}

/** Status log: the latest entry and the history count (opens W4, where an update is added). */
export function StatusLogSummary({ detail }: { detail: RowDetail }) {
  const latest = detail.latest_status
  return (
    <div className="space-y-0.5 text-[13px]" data-testid="status-summary">
      {latest ? (
        <p className="flex flex-wrap items-center gap-x-2">
          <span className="inline-flex items-center gap-1.5 font-medium">
            <Dot colour={latest.colour} what="Status" />
            {latest.label}
          </span>
          {latest.team && <span className="text-slate-600">· {latest.team}</span>}
          <span className="text-xs text-slate-500">{latest.author_user_key}</span>
        </p>
      ) : (
        <p className="text-slate-500">No status set (the system RAG applies).</p>
      )}
      {latest && <p className="text-slate-700">{latest.comment}</p>}
      <p className="text-xs text-slate-500">
        {detail.status_log_count} {detail.status_log_count === 1 ? 'entry' : 'entries'} in the log
      </p>
    </div>
  )
}

/** Samples: the count per status (opens W5). */
export function SamplesSummary({ detail }: { detail: RowDetail }) {
  const counts = sampleCounts(detail.samples)
  if (counts.all === 0) return <p className="text-[13px] text-slate-500">No samples recorded for this lot.</p>
  return (
    <p className="text-[13px]" data-testid="samples-summary">
      {counts.all} {counts.all === 1 ? 'sample' : 'samples'}: {counts.received} received · {counts.approved} approved
      {counts.rejected > 0 ? ` · ${counts.rejected} rejected` : ''}
    </p>
  )
}

/** Need-by: system and adjusted dates, the reason and who set it, with the plan's expected completion (opens W6). */
export function NeedBySummary({ detail }: { detail: RowDetail }) {
  const plan = detail.plan
  const rag = plan.rag as keyof typeof RAG_TEXT | null
  const adjusted = detail.current_overrides.adjusted_need_by_date
  const effective = Object.values(plan.effective_slas as Record<string, number>)
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[13px]" data-testid="needby-summary">
      <dt className="text-slate-500">System need-by</dt>
      <dd className={detail.adjusted_need_by_date ? 'text-slate-400 line-through' : ''}>{formatDate(detail.system_need_by_locked)}</dd>
      <dt className="text-slate-500">Adjusted need-by</dt>
      <dd className={detail.adjusted_need_by_date ? 'italic' : 'text-slate-500'} data-testid="operative-need-by">
        {detail.adjusted_need_by_date ? formatDate(detail.adjusted_need_by_date) : 'None set'}
      </dd>
      {detail.adjusted_need_by_date && (
        <>
          <dt className="text-slate-500">Reason</dt>
          <dd>{humanize(detail.adjusted_reason_code ?? 'adjusted')}</dd>
          <dt className="text-slate-500">Set by</dt>
          <dd>{adjusted?.author_user_key ?? '—'}</dd>
        </>
      )}
      <dt className="text-slate-500">Expected completion</dt>
      <dd data-testid="expected-completion">
        {formatDate(plan.expected_completion)}
        {rag ? <span className={`ml-2 font-medium ${RAG_TEXT[rag]}`}>{rag.toUpperCase()}</span> : null}
        {plan.days_remaining !== null && plan.days_remaining < 0 ? <span className="ml-2 text-red-700">{-plan.days_remaining} d late</span> : null}
        {plan.expected_completion ? (
          <ExplainPopover
            what="expected completion"
            path={`/rows/${encodeURIComponent(detail.row_key)}/explain`}
            params={new URLSearchParams({ field: 'expected_completion' })}
            className="ml-2"
          />
        ) : null}
      </dd>
      <dt className="text-slate-500">Compression</dt>
      <dd>{plan.compressed ? `Compressed to ${Math.round(Number(plan.compression_ratio) * 100)}% (${effective.join(' / ')} d)` : 'None'}</dd>
      {plan.late_reason_auto ? (
        <>
          <dt className="text-slate-500">Late reason</dt>
          <dd>{humanize(plan.late_reason_auto)}</dd>
        </>
      ) : null}
    </dl>
  )
}

export function SourceRefs({ detail }: { detail: RowDetail }) {
  const facts = detail.facts as Record<string, unknown>
  return (
    <details className="text-[13px]">
      <summary className="cursor-pointer text-slate-600">Source references</summary>
      <pre className="mt-2 overflow-auto rounded-chip bg-slate-50 p-3 text-xs">{JSON.stringify(facts.source_refs_json ?? {}, null, 2)}</pre>
    </details>
  )
}
