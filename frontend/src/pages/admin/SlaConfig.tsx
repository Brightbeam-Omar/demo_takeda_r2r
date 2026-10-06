import { useReference } from '../../api/queries'
import { PageIntro } from '../../components/admin/PageIntro'
import { ErrorState, Skeleton } from '../../components/common/States'

interface StageRow {
  stage_key: string
  label: string
  sla_days: number
  reeval_sla_days: number | null
  team: string
  show_card: boolean
  terminal: boolean
}

interface MetricRow {
  metric_id: string
  label: string
  sla_days: number | null
  entry_event: string | null
  exit_event: string | null
  window: string
  status: string
}

const dash = (value: string | number | null | undefined) => (value === null || value === undefined || value === '' ? '—' : String(value))
const head = 'px-3 py-2 text-[11px] font-semibold tracking-wider text-ink-2 uppercase'

/** SLA Configuration (F21-FR-06): the SLAs of the site profile, read-only. */
export function SlaConfig() {
  const reference = useReference()
  const data = reference.data
  const stages = (data?.stages ?? []) as unknown as StageRow[]
  const metrics = (data?.metrics ?? []) as unknown as MetricRow[]
  return (
    <main className="flex-1 space-y-4 overflow-auto p-6 pb-20" data-testid="sla-config-page">
      <PageIntro subtitle="Read-only: the service levels the plan dates, RAG and metrics are measured against" />
      {reference.isError && !data ? <ErrorState what="the SLA configuration" error={reference.error} onRetry={() => void reference.refetch()} /> : null}
      {!data && reference.isPending ? <Skeleton label="SLA configuration" height="h-48" /> : null}
      {data ? (
        <>
          <p className="rounded-card border border-hairline bg-panel px-4 py-3 text-sm text-ink" data-testid="sla-note">
            Configured in the site profile <code className="font-mono">{data.profile_file}</code>; changes take effect at the next pipeline run.
          </p>
          <section aria-label="Stages" className="space-y-2">
            <h2 className="text-sm font-semibold tracking-wide text-ink-2 uppercase">Stages</h2>
            <table className="w-full rounded-card border border-hairline bg-white text-left text-[13px]" data-testid="sla-stages">
              <thead>
                <tr>
                  <th className={head}>Stage</th>
                  <th className={head}>SLA (days)</th>
                  <th className={head}>Re-eval SLA (days)</th>
                  <th className={head}>Team</th>
                  <th className={head}>Card shown</th>
                </tr>
              </thead>
              <tbody>
                {stages.map((stage) => (
                  <tr key={stage.stage_key} data-testid="sla-stage" className="border-t border-hairline">
                    <td className="px-3 py-2 font-medium">{stage.label}</td>
                    <td className="px-3">{stage.terminal ? '—' : stage.sla_days}</td>
                    <td className="px-3">{dash(stage.reeval_sla_days)}</td>
                    <td className="px-3">{stage.team}</td>
                    <td className="px-3">{stage.show_card ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section aria-label="Metrics" className="space-y-2">
            <h2 className="text-sm font-semibold tracking-wide text-ink-2 uppercase">Metrics</h2>
            <table className="w-full rounded-card border border-hairline bg-white text-left text-[13px]" data-testid="sla-metrics">
              <thead>
                <tr>
                  <th className={head}>Metric</th>
                  <th className={head}>Entry</th>
                  <th className={head}>Exit</th>
                  <th className={head}>SLA (days)</th>
                  <th className={head}>Window</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((metric) => (
                  <tr key={metric.metric_id} data-testid="sla-metric" className="border-t border-hairline align-top">
                    <td className="px-3 py-2 font-medium">
                      {metric.metric_id} · {metric.label}
                    </td>
                    <td className="px-3 whitespace-normal">{dash(metric.entry_event)}</td>
                    <td className="px-3 whitespace-normal">{dash(metric.exit_event)}</td>
                    <td className="px-3">{dash(metric.sla_days)}</td>
                    <td className="px-3">{metric.window}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </main>
  )
}
