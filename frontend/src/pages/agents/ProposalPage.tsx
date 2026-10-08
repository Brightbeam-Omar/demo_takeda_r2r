import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApprove, useProposal, useReject, useRunAgent, useTrace, runErrorText, type ProposalDetailData } from '../../api/agents'
import { useMe, useReference } from '../../api/queries'
import { EvidenceTable, ValidatorChecklist } from '../../components/agents/Evidence'
import { ExecutedPreview } from '../../components/agents/ExecutedPreview'
import { PriorityChip, ProposalPill } from '../../components/agents/ProposalPill'
import { ProviderChip } from '../../components/agents/ProviderChip'
import { Modal } from '../../components/common/Modal'
import { ErrorState, Skeleton } from '../../components/common/States'
import { formatClock, humanize, withSiteTimes } from '../../lib/format'
import { roleLabel } from '../../components/shell/PersonaSwitcher'
import { READ_ONLY_HINT, canDecideProposal, canRunAgent } from '../../lib/roles'

const MIN_REASON = 3
const MAX_REASON = 200

function RejectDialog({ busy, error, onCancel, onSubmit }: { busy: boolean; error: string | null; onCancel: () => void; onSubmit: (reason: string) => void }) {
  const [reason, setReason] = useState('')
  const length = reason.trim().length
  const valid = length >= MIN_REASON && length <= MAX_REASON
  return (
    <Modal open onClose={onCancel} title="Reject this proposal" size="window" testId="reject-dialog">
      <label className="block text-sm font-medium text-ink" htmlFor="reject-reason">
        Reason ({MIN_REASON}–{MAX_REASON} characters)
      </label>
      <textarea
        id="reject-reason"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        maxLength={MAX_REASON}
        rows={3}
        className="mt-1 w-full rounded-chip border border-slate-300 p-2 text-sm"
      />
      {error ? (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          disabled={!valid || busy}
          className="rounded-chip bg-red-600 px-3 py-1.5 text-sm font-medium text-white enabled:hover:opacity-90 disabled:opacity-40"
          onClick={() => onSubmit(reason.trim())}
        >
          Reject
        </button>
      </div>
    </Modal>
  )
}

function Decision({ proposal }: { proposal: ProposalDetailData }) {
  const approve = useApprove(proposal.id)
  const reject = useReject(proposal.id)
  const run = useRunAgent()
  const me = useMe()
  const [rejecting, setRejecting] = useState(false)
  const role = me.data?.role
  const decider = canDecideProposal(role, proposal.required_role)
  const hint = decider ? undefined : `Needs the ${roleLabel(proposal.required_role)} role`
  if (proposal.status === 'pending_approval') {
    return (
      <div className="flex flex-wrap items-center gap-3" data-testid="decision">
        <button
          type="button"
          disabled={!decider || approve.isPending}
          title={hint}
          className="rounded-chip bg-accent px-4 py-1.5 text-sm font-medium text-white enabled:hover:opacity-90 disabled:opacity-40"
          onClick={() => approve.mutate()}
        >
          {approve.isPending ? 'Approving…' : 'Approve'}
        </button>
        <button
          type="button"
          disabled={!decider}
          title={hint}
          className="rounded-chip border border-slate-300 bg-white px-4 py-1.5 text-sm enabled:hover:border-slate-400 disabled:opacity-40"
          onClick={() => setRejecting(true)}
        >
          Reject
        </button>
        {approve.isError ? (
          <p role="alert" className="text-sm text-red-700">
            {approve.error.message}
          </p>
        ) : null}
        {!decider ? <p className="text-sm text-ink-2">Only {roleLabel(proposal.required_role)} (or Admin) can decide.</p> : null}
        {rejecting ? (
          <RejectDialog
            busy={reject.isPending}
            error={reject.isError ? reject.error.message : null}
            onCancel={() => setRejecting(false)}
            onSubmit={(reason) => reject.mutate(reason, { onSuccess: () => setRejecting(false) })}
          />
        ) : null}
      </div>
    )
  }
  if (proposal.status === 'rejected_by_validator') {
    const failure = run.isError ? runErrorText(run.error) : null
    return (
      <div className="space-y-2" data-testid="decision">
        <p className="text-sm text-ink-2">The validator rejected this draft. No one can approve it; the way forward is to run the agent again.</p>
        <button
          type="button"
          disabled={!canRunAgent(role) || run.isPending || !proposal.row_key}
          title={canRunAgent(role) ? undefined : READ_ONLY_HINT}
          className="rounded-chip border border-slate-300 bg-white px-4 py-1.5 text-sm enabled:hover:border-slate-400 disabled:opacity-40"
          onClick={() => run.mutate(proposal.row_key ?? undefined)}
        >
          {run.isPending ? 'Running…' : 'Run again'}
        </button>
        {failure ? (
          <p role="alert" className="text-sm text-red-700">
            {failure.message} {failure.hint}
          </p>
        ) : run.data?.created[0] ? (
          <p className="text-sm">
            New proposal:{' '}
            <Link className="text-accent hover:underline" to={`/agents/proposals/${run.data.created[0].proposal_id}`}>
              #{run.data.created[0].proposal_id}
            </Link>
          </p>
        ) : null}
      </div>
    )
  }
  return null
}

/** `/agents/proposals/:id`: the draft, its evidence and the validator's checklist, the decision, and what approval produced. */
export function ProposalPage() {
  const id = Number(useParams().id)
  const proposal = useProposal(id)
  const reference = useReference()
  const timezone = reference.data?.site_timezone ?? 'UTC'
  const data = proposal.data
  const trace = useTrace(data?.trace_id ?? '') // the provider chip reads the run's provider and model from its trace
  return (
    <main className="flex-1 space-y-5 overflow-auto p-6 pb-20" data-testid="proposal-page">
      <Link to="/agents" className="text-sm text-accent hover:underline">
        ← Agents
      </Link>
      {proposal.isError ? <ErrorState what="the proposal" error={proposal.error} onRetry={() => void proposal.refetch()} /> : null}
      {!data && proposal.isPending ? <Skeleton label="proposal" height="h-64" /> : null}
      {data ? (
        <>
          <header className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold text-ink">
              Proposal #{data.id} · Air-gap ticket for {data.batch_no ?? data.row_key}
            </h2>
            <ProposalPill status={data.status} />
            <PriorityChip priority={data.priority} />
            <ProviderChip provider={trace.data?.provider ?? null} modelId={trace.data?.model_id ?? null} />
            {data.trace_id ? (
              <Link to={`/agents/traces/${data.trace_id}`} className="ml-auto text-sm text-accent hover:underline" data-testid="view-trace">
                View trace {data.trace_id} ↗
              </Link>
            ) : null}
          </header>

          {data.status === 'rejected_by_validator' && data.validator?.headline ? (
            <p role="alert" data-testid="validator-headline" className="rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800">
              {data.validator.headline}
            </p>
          ) : null}
          {data.status === 'rejected' && data.decision_reason ? (
            <p className="rounded-card border border-hairline bg-panel px-4 py-3 text-sm" data-testid="reject-reason">
              Rejected by {data.decided_by}: {data.decision_reason}
            </p>
          ) : null}

          {data.payload && !data.payload.error ? (
            <section aria-label="Draft" className="rounded-card border border-hairline bg-white p-5" data-testid="draft">
              <h3 className="text-base font-semibold text-ink">{data.payload.title}</h3>
              <p className="mt-2 max-w-4xl text-sm">{withSiteTimes(data.payload.summary, timezone)}</p>
              <dl className="mt-4 grid grid-cols-4 gap-4 text-[13px]">
                <div>
                  <dt className="text-[11px] font-semibold tracking-wide text-ink-2 uppercase">Hours in the gap</dt>
                  <dd className="mt-0.5">{data.payload.hours_in_gap} h</dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold tracking-wide text-ink-2 uppercase">Recommended action</dt>
                  <dd className="mt-0.5">{humanize(data.payload.recommended_action)}</dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold tracking-wide text-ink-2 uppercase">Open deviations</dt>
                  <dd className="mt-0.5 font-mono">{data.payload.open_deviations.length ? data.payload.open_deviations.join(', ') : 'none'}</dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold tracking-wide text-ink-2 uppercase">Assigned to</dt>
                  <dd className="mt-0.5">{roleLabel(data.payload.recipient_role)}</dd>
                </div>
              </dl>
            </section>
          ) : (
            <p className="rounded-card border border-dashed border-slate-300 bg-white px-4 py-4 text-sm text-ink-2" data-testid="no-draft">
              The run produced no ticket{data.error ? `: ${data.error}` : '.'}
            </p>
          )}

          {data.evidence.length > 0 ? (
            <section aria-label="Evidence" className="rounded-card border border-hairline bg-white p-5">
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-ink-2 uppercase">Evidence</h3>
              <EvidenceTable evidence={data.evidence} validator={data.validator} timezone={timezone} />
            </section>
          ) : null}

          {data.validator ? (
            <section aria-label="Validator" className="rounded-card border border-hairline bg-white p-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-semibold tracking-wide text-ink-2 uppercase">Validator checklist</h3>
                <span className={`text-sm font-semibold ${data.validator.passed ? 'text-emerald-700' : 'text-red-700'}`}>
                  {data.validator.passed ? 'All rules passed' : 'Failed'}
                </span>
              </div>
              <ValidatorChecklist validator={data.validator} />
              <p className="mt-2 text-xs text-ink-2">Checked {formatClock(data.validator.checked_at, timezone)}. Approve checks every rule again against the live sources.</p>
            </section>
          ) : null}

          <Decision proposal={data} />

          {data.status === 'executed' ? (
            <>
              <p className="text-sm" data-testid="decided-line">
                Approved by {data.decided_by} on {data.decided_at ? formatClock(data.decided_at, timezone) : ''}.
              </p>
              <ExecutedPreview actions={data.actions} />
            </>
          ) : null}
        </>
      ) : null}
    </main>
  )
}
