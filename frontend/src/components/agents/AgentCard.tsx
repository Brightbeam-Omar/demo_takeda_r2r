import { ProviderChip } from './ProviderChip'
import { runErrorText, useRunAgent, type AgentCardData } from '../../api/agents'
import { formatClock } from '../../lib/format'
import { READ_ONLY_HINT } from '../../lib/roles'

interface Props {
  agent: AgentCardData
  timezone: string
}

/** The air-gap agent: what it does, which model and prompt it runs, when it last ran, and Run now (F12-FR-12 a). */
export function AgentCard({ agent, timezone }: Props) {
  const run = useRunAgent()
  const failure = run.isError ? runErrorText(run.error) : null
  const created = run.data?.created.length ?? 0
  return (
    <section aria-label={agent.name} data-testid="agent-card" className="rounded-card border border-hairline bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          <h2 className="text-lg font-semibold text-ink">{agent.name}</h2>
          <p className="mt-1 text-sm text-ink-2">{agent.purpose}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <button
            type="button"
            disabled={!agent.can_run || run.isPending}
            title={agent.can_run ? undefined : READ_ONLY_HINT}
            className="rounded-chip bg-accent px-4 py-1.5 text-sm font-medium text-white enabled:hover:opacity-90 disabled:opacity-40"
            onClick={() => run.mutate(undefined)}
          >
            {run.isPending ? 'Running…' : 'Run now'}
          </button>
          <p className="text-xs text-ink-2" data-testid="agent-last-run">
            {agent.last_run_at ? `Last run ${formatClock(agent.last_run_at, timezone)}` : 'Not run yet'}
          </p>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-4 gap-4 text-[13px]">
        <div>
          <dt className="text-[11px] font-semibold tracking-wide text-ink-2 uppercase">Model</dt>
          <dd className="mt-0.5 flex items-center gap-1.5" data-testid="agent-model">
            <ProviderChip provider={agent.provider} modelId={agent.model_id} />
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold tracking-wide text-ink-2 uppercase">Prompt version</dt>
          <dd className="mt-0.5 font-mono" data-testid="agent-prompt">
            {agent.prompt_version}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-[11px] font-semibold tracking-wide text-ink-2 uppercase">Read-only tools</dt>
          <dd className="mt-0.5 flex flex-wrap gap-1">
            {agent.tools.map((tool) => (
              <span key={tool} className="rounded-chip bg-panel px-1.5 py-px font-mono text-xs">
                {tool}
              </span>
            ))}
          </dd>
        </div>
      </dl>
      <div aria-live="polite" className="mt-3 text-sm empty:hidden">
        {failure ? (
          <p role="alert" data-testid="run-error" className="rounded-card border border-red-200 bg-red-50 px-3 py-2 text-red-800">
            <strong>{failure.message}</strong> {failure.hint}
            {failure.key ? <span className="ml-1 font-mono text-xs">Key {failure.key.slice(0, 16)}…</span> : null}
          </p>
        ) : run.data ? (
          <p data-testid="run-result" className="text-ink-2">
            {created > 0
              ? `${created} ${created === 1 ? 'proposal' : 'proposals'} created.`
              : 'Nothing new to propose: every air-gap batch already has an open proposal.'}
          </p>
        ) : null}
      </div>
    </section>
  )
}
