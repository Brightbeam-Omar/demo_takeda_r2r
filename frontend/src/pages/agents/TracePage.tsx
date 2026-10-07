import { Link, useParams } from 'react-router-dom'
import { useTrace } from '../../api/agents'
import { TraceTimeline } from '../../components/agents/TraceTimeline'
import { ErrorState, Skeleton } from '../../components/common/States'

const money = (value: number) => `$${value.toFixed(4)}`

/** `/agents/traces/:traceId`: every step of a run in order, with tokens, latency and the cost estimate (F12-FR-12 d). */
export function TracePage() {
  const traceId = useParams().traceId ?? ''
  const trace = useTrace(traceId)
  const data = trace.data
  return (
    <main className="flex-1 space-y-5 overflow-auto p-6 pb-20" data-testid="trace-page">
      <Link to={data?.proposal_id ? `/agents/proposals/${data.proposal_id}` : '/agents'} className="text-sm text-accent hover:underline">
        ← {data?.proposal_id ? `Proposal #${data.proposal_id}` : 'Agents'}
      </Link>
      {trace.isError ? <ErrorState what="the trace" error={trace.error} onRetry={() => void trace.refetch()} /> : null}
      {!data && trace.isPending ? <Skeleton label="trace" height="h-64" /> : null}
      {data ? (
        <>
          <header className="flex flex-wrap items-center gap-3">
            <h2 className="font-mono text-lg font-semibold text-ink">{data.trace_id}</h2>
            <span className="rounded-chip border border-hairline px-1.5 text-[11px] font-semibold uppercase" data-testid="trace-provider">
              {data.provider}
              {data.replayed ? ' · replayed' : ''}
            </span>
            <span className="font-mono text-sm text-ink-2">{data.model_id}</span>
          </header>
          <dl className="grid grid-cols-5 gap-3 text-[13px]" data-testid="trace-totals">
            {[
              ['Model calls', String(data.totals.model_calls)],
              ['Tokens in', String(data.totals.tokens_in)],
              ['Tokens out', String(data.totals.tokens_out)],
              ['Latency', `${data.totals.latency_ms} ms`],
              ['Cost estimate', money(data.totals.cost_usd)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-card border border-hairline bg-white px-3 py-2">
                <dt className="text-[11px] font-semibold tracking-wide text-ink-2 uppercase">{label}</dt>
                <dd className="mt-0.5 text-base font-semibold">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-ink-2">
            The estimate is tokens times the prices in the environment settings.
            {data.replayed ? ' Tokens and latency are the recorded ones: a replay does not call the model.' : ''}
          </p>
          <TraceTimeline steps={data.steps} />
        </>
      ) : null}
    </main>
  )
}
