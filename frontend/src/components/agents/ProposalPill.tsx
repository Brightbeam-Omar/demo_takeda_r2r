import type { ProposalStatus } from '../../api/agents'

export const STATUS_LABEL: Record<ProposalStatus, string> = {
  pending_approval: 'Pending approval',
  rejected_by_validator: 'Rejected by validator',
  approved: 'Approved',
  rejected: 'Rejected',
  executed: 'Executed',
}

const TONE: Record<ProposalStatus, string> = {
  pending_approval: 'border-amber-200 bg-amber-50 text-amber-800',
  rejected_by_validator: 'border-red-200 bg-red-50 text-red-800',
  approved: 'border-sky-200 bg-sky-50 text-sky-800',
  rejected: 'border-slate-300 bg-slate-100 text-slate-700',
  executed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
}

/** The status of an agent proposal, in the same pill everywhere it appears (Insights window, drawer, Agents). */
export function ProposalPill({ status }: { status: ProposalStatus }) {
  return (
    <span data-status={status} className={`inline-block rounded-pill border px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${TONE[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  )
}

export function PriorityChip({ priority }: { priority: 'high' | 'normal' | null | undefined }) {
  if (!priority) return <span className="text-slate-400">—</span>
  return (
    <span
      data-priority={priority}
      className={`inline-block rounded-chip border px-1.5 py-px text-[10px] font-semibold tracking-wide uppercase ${priority === 'high' ? 'border-red-300 text-red-700' : 'border-slate-300 text-slate-600'}`}
    >
      {priority}
    </span>
  )
}
