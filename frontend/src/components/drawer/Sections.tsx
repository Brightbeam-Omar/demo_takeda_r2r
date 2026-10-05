import type { ReactNode } from 'react'
import type { RowDetail } from '../../api/queries'
import { formatDate, formatShortDate, humanize } from '../../lib/format'
import { ExplainPopover } from '../explain/ExplainPopover'
import { Light } from '../table/cells'

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

const RAG_TEXT = { red: 'text-red-700', amber: 'text-amber-700', green: 'text-emerald-700' }

export function PlanSection({ detail }: { detail: RowDetail }) {
  const plan = detail.plan
  const rag = plan.rag as keyof typeof RAG_TEXT | null
  const effective = Object.entries(plan.effective_slas as Record<string, number>)
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[13px]">
      <dt className="text-slate-500">System need-by</dt>
      <dd className={detail.adjusted_need_by_date ? 'text-slate-400 line-through' : ''}>
        {formatDate(detail.system_need_by_locked)}
      </dd>
      <dt className="text-slate-500">Operative need-by</dt>
      <dd className={detail.adjusted_need_by_date ? 'italic' : ''} data-testid="operative-need-by">
        {formatDate(detail.operative_need_by)}
        {detail.adjusted_need_by_date ? ` (${humanize(detail.adjusted_reason_code ?? 'adjusted')})` : ''}
      </dd>
      <dt className="text-slate-500">Expected completion</dt>
      <dd data-testid="expected-completion">
        {formatDate(plan.expected_completion)}
        {rag ? <span className={`ml-2 font-medium ${RAG_TEXT[rag]}`}>{rag.toUpperCase()}</span> : null}
        {plan.days_remaining !== null && plan.days_remaining < 0 ? (
          <span className="ml-2 text-red-700">{-plan.days_remaining} d late</span>
        ) : null}
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
      <dd>
        {plan.compressed
          ? `Compressed to ${Math.round(Number(plan.compression_ratio) * 100)}% (${effective.map(([, days]) => days).join(' / ')} d)`
          : 'None'}
      </dd>
      {plan.late_reason_auto ? (
        <>
          <dt className="text-slate-500">Late reason</dt>
          <dd>{humanize(plan.late_reason_auto)}</dd>
        </>
      ) : null}
    </dl>
  )
}

const SEVERITY = { critical: 'text-red-700', major: 'text-amber-700', minor: 'text-slate-600' }

export function QualitySection({ detail }: { detail: RowDetail }) {
  const facts = detail.facts as Record<string, unknown>
  return (
    <div className="space-y-3 text-[13px]">
      <div className="flex items-center gap-2">
        <Light colour={detail.inbound_light} what="Inbound check" />
        <span>
          Inbound check: {humanize(String(facts.inbound_check_status ?? 'none'))}
          {facts.inbound_check_completed_date ? ` on ${formatDate(String(facts.inbound_check_completed_date))}` : ''}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Light colour={detail.deviation_light} what="Deviations" />
        <span>
          {detail.deviations.length === 0
            ? 'No deviations linked to this batch'
            : `${detail.deviations.length} linked ${detail.deviations.length === 1 ? 'deviation' : 'deviations'}`}
        </span>
      </div>
      <ul className="space-y-1" data-testid="deviation-list">
        {detail.deviations.map((deviation) => (
          <li key={deviation.deviation_no} className="rounded-chip border border-slate-200 px-3 py-1.5">
            <span className="font-medium">{deviation.deviation_no}</span> {deviation.title}
            <div className="text-xs text-slate-500">
              <span className={SEVERITY[(deviation.severity ?? 'minor') as keyof typeof SEVERITY]}>
                {humanize(deviation.severity ?? '')}
              </span>
              {' · '}
              {humanize(deviation.status ?? '')}
              {deviation.opened_on ? ` · opened ${formatShortDate(deviation.opened_on)}` : ''}
              {deviation.owner ? ` · ${deviation.owner}` : ''}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

const FIELD_LABELS: Record<string, string> = {
  adjusted_need_by_date: 'Need-by',
  expedite: 'Expedite',
  manual_status: 'Status',
}

function describe(field: string, value: unknown): string {
  if (value === null || value === undefined) return 'cleared'
  if (field === 'adjusted_need_by_date') return formatDate(String(value))
  if (field === 'manual_status') {
    const status = value as { rag?: string; team?: string }
    return `${(status.rag ?? '').toUpperCase()}${status.team ? ` · ${status.team}` : ''}`
  }
  return String(value)
}

export function HumanInputSection({ detail }: { detail: RowDetail }) {
  const history = detail.override_history
  if (history.length === 0) return <p className="text-[13px] text-slate-500">No human input yet. All values come from the pipeline.</p>
  return (
    <table className="w-full text-left text-[13px]" data-testid="override-history">
      <thead className="text-xs text-slate-500 uppercase">
        <tr>
          <th className="py-1 font-medium">Field</th>
          <th className="font-medium">Value</th>
          <th className="font-medium">By</th>
          <th className="font-medium">When</th>
        </tr>
      </thead>
      <tbody>
        {history.map((entry) => (
          <tr key={entry.id} className={`border-t border-slate-100 ${entry.is_current ? 'font-medium' : 'text-slate-500'}`}>
            <td className="py-1.5">
              {FIELD_LABELS[entry.field] ?? entry.field} v{entry.version}
              {entry.is_current ? <span className="ml-1 text-xs text-indigo-700">current</span> : null}
            </td>
            <td className="italic">
              {describe(entry.field, entry.value)}
              {entry.reason_code ? <div className="text-xs not-italic text-slate-500">{humanize(entry.reason_code)}</div> : null}
              {entry.note ? <div className="text-xs not-italic text-slate-500">{entry.note}</div> : null}
            </td>
            <td>{entry.author_user_key}</td>
            <td>{formatShortDate(entry.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function SourceRefs({ detail }: { detail: RowDetail }) {
  const facts = detail.facts as Record<string, unknown>
  return (
    <details className="text-[13px]">
      <summary className="cursor-pointer text-slate-600">Source references</summary>
      <pre className="mt-2 overflow-auto rounded-chip bg-slate-50 p-3 text-xs">
        {JSON.stringify(facts.source_refs_json ?? {}, null, 2)}
      </pre>
    </details>
  )
}
