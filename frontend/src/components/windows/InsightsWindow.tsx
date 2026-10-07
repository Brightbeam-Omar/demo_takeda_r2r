import { Link } from 'react-router-dom'
import { runErrorText, useRunAgent, type ProposalStatus } from '../../api/agents'
import { useInsights, useMe, useReference } from '../../api/queries'
import type { Insights } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { READ_ONLY_HINT, canRunAgent } from '../../lib/roles'
import { ProposalPill } from '../agents/ProposalPill'
import { EmptyState, ErrorState, Skeleton } from '../common/States'
import { DataTable, type Column } from '../datatable/DataTable'
import { Modal } from '../common/Modal'

type Entry = Insights['rows'][number]

/** Green under 2 days, amber 2–5, red over 5 (F16-FR-09). A gap is at least a day (OQ-088). */
export function gapTone(days: number): 'green' | 'amber' | 'red' {
  if (days < 2) return 'green'
  return days <= 5 ? 'amber' : 'red'
}

const TONE = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  amber: 'border-amber-200 bg-amber-50 text-amber-800',
  red: 'border-red-200 bg-red-50 text-red-800',
}

export function GapChip({ days }: { days: number }) {
  return (
    <span data-tone={gapTone(days)} className={`inline-block rounded-pill border px-2 py-0.5 text-xs font-semibold ${TONE[gapTone(days)]}`}>
      {days}d
    </span>
  )
}

interface Props {
  open: boolean
  onClose: () => void
  /** The Overview filters except stage, in the API's form. */
  params: URLSearchParams
}

/** Runs the air-gap agent for every air-gap batch without an open proposal (F12-FR-13, OQ-141). */
function RunButton() {
  const me = useMe()
  const run = useRunAgent()
  const allowed = canRunAgent(me.data?.role)
  const failure = run.isError ? runErrorText(run.error) : null
  const created = run.data?.created.length ?? 0
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3" data-testid="insights-run">
      <div className="text-sm" aria-live="polite">
        {failure ? (
          <p role="alert" className="text-red-800" data-testid="run-error">
            {failure.message} {failure.hint}
            {failure.key ? <span className="ml-1 font-mono text-xs">({failure.key.slice(0, 12)}…)</span> : null}
          </p>
        ) : run.data ? (
          <p className="text-slate-600" data-testid="run-result">
            {created > 0
              ? `${created} ${created === 1 ? 'proposal' : 'proposals'} created.`
              : 'Nothing new to propose: every batch already has an open proposal.'}
          </p>
        ) : null}
      </div>
      <button
        type="button"
        disabled={!allowed || run.isPending}
        title={allowed ? undefined : READ_ONLY_HINT}
        className="rounded-chip bg-accent px-3 py-1.5 text-sm font-medium text-white enabled:hover:opacity-90 disabled:opacity-40"
        onClick={() => run.mutate(undefined)}
      >
        {run.isPending ? 'Running…' : 'Run air-gap agent'}
      </button>
    </div>
  )
}

export function InsightsWindow({ open, onClose, params }: Props) {
  const terms = useTerms()
  const reference = useReference()
  const insights = useInsights(params, open)
  const total = insights.data?.total ?? 0
  const qaRelease = String((reference.data?.stages ?? []).find((stage) => stage.stage_key === 'qa_release')?.label ?? 'QA Release')
  const columns: Column<Entry>[] = [
    { id: 'batch', header: 'Batch', cell: (r) => r.batch_no, text: (r) => r.batch_no },
    {
      id: 'material',
      header: 'Material',
      cell: (r) => (
        <>
          <div>{r.material_no}</div>
          <div className="text-xs text-slate-500">{r.material_desc}</div>
        </>
      ),
      text: (r) => `${r.material_no} ${r.material_desc ?? ''}`,
    },
    { id: 'stage', header: 'Stage', cell: (r) => r.stage_label, text: (r) => r.stage_label },
    { id: 'gap', header: 'Days Gap', cell: (r) => <GapChip days={r.days_gap} />, text: (r) => `${r.days_gap}d`, sortValue: (r) => r.days_gap },
    {
      id: 'proposal',
      header: 'Proposal',
      text: (r) => (r.proposal ? r.proposal.status : 'none'),
      cell: (r) =>
        r.proposal ? (
          <Link to={`/agents/proposals/${r.proposal.id}`} data-testid="proposal-link" aria-label={`Open proposal ${r.proposal.id} for ${r.batch_no}`}>
            <ProposalPill status={r.proposal.status as ProposalStatus} />
          </Link>
        ) : (
          <span className="text-slate-400">—</span>
        ),
    },
  ]
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${terms.insights_banner} — ${total} affected ${total === 1 ? 'batch' : 'batches'}`}
      description={`Batches where ${terms.lims} is approved but ${terms.erp} has not received the result. Flagged after ${reference.data?.air_gap_threshold_hours ?? 24}+ hours — each day erodes the ${qaRelease} SLA. Sorted worst-first.`}
    >
      {insights.isError ? (
        <ErrorState what="the insights" error={insights.error} onRetry={() => void insights.refetch()} />
      ) : !insights.data ? (
        <Skeleton label="insights" height="h-40" />
      ) : insights.data.rows.length === 0 ? (
        <EmptyState>{`No ${terms.insights_banner} in this period.`}</EmptyState>
      ) : (
        <>
          <RunButton />
          <DataTable
            rows={insights.data.rows}
            columns={columns}
            exportName="insights"
            rowKey={(r) => r.row_key}
            unit={['batch', 'batches']}
            columnsKey="insights"
            rowTestId="window-row"
          />
        </>
      )}
    </Modal>
  )
}
