import type { Metrics } from '../../api/queries'
import { ExplainPopover } from '../explain/ExplainPopover'
import { Sparkline } from './Sparkline'

type Metric = Metrics['metrics'][number]

const BAR: Record<string, string> = { green: 'bg-rag-green', amber: 'bg-rag-amber', red: 'bg-rag-red' }

const pct = (value: string | number | null | undefined): number | null =>
  value === null || value === undefined ? null : Number(value)

interface Props {
  metric: Metric
  /** Label of the stage the metric measures, for the tooltip. */
  stageLabel?: string
}

/**
 * F17-FR-06. `METRIC n` / name / big % / `SLA 7d · on_time/completed ⓘ`, with a 4 px top bar in the RAG colour.
 * The headline is the last complete week; the week to date is the small secondary value (03 section 7). A metric
 * still waiting for its signal reads N/A with the reason in the ⓘ tooltip.
 */
export function MetricCard({ metric, stageLabel }: Props) {
  const number = metric.metric_id.replace(/^\D+/, '')
  const heading = (
    <>
      <div className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Metric {number}</div>
      <div className="truncate text-sm font-medium text-ink" title={metric.label}>
        {metric.label}
      </div>
    </>
  )
  if (metric.status === 'awaiting_signal') {
    const reason = metric.null_reason ?? 'Awaiting signal'
    return (
      <div data-testid={`metric-${metric.metric_id}`} className="relative overflow-hidden rounded-card border border-hairline bg-white px-3 pt-3.5 pb-2">
        {heading}
        <div className="mt-1 text-2xl font-semibold text-ink-3" data-testid="metric-headline">
          N/A
        </div>
        <div className="text-xs text-ink-2">
          Awaiting signal{' '}
          <span role="img" aria-label={`${metric.label}: no data. ${reason}`} title={`${metric.label}: ${reason}`} className="cursor-help" data-testid="metric-info">
            ⓘ
          </span>
        </div>
      </div>
    )
  }
  const weeks = metric.weeks
  const complete = weeks.slice(0, -1)
  const headline = complete[complete.length - 1]
  const toDate = weeks[weeks.length - 1]
  const rag = headline?.rag ?? ''
  const sla = metric.sla_days ? `SLA ${metric.sla_days}d` : 'SLA –'
  const counts = headline ? `${headline.on_time}/${headline.completed}` : '–'
  const how = `${metric.label}: the share of ${stageLabel ?? 'stage'} completions in the week that finished within the SLA (${metric.sla_days ?? '–'} d; re-evaluation lots use their own SLA). Source: weekly_metrics_v.`
  return (
    <div data-testid={`metric-${metric.metric_id}`} data-rag={rag || undefined} className="relative overflow-hidden rounded-card border border-hairline bg-white px-3 pt-3.5 pb-2">
      {BAR[rag] && <div data-testid="metric-bar" className={`absolute inset-x-0 top-0 h-1 ${BAR[rag]}`} />}
      {heading}
      <div className="mt-1 text-2xl font-semibold tabular-nums">
        <ExplainPopover
          what={metric.metric_id}
          path="/explain"
          params={new URLSearchParams({ field: `metric:${metric.metric_id}`, ...(headline ? { week: headline.week_start } : {}) })}
          className="text-2xl font-semibold text-ink hover:text-accent"
        >
          <span data-testid="metric-headline">{headline && headline.pct !== null ? `${Number(headline.pct).toFixed(0)}%` : '–'}</span>
        </ExplainPopover>
      </div>
      <div className="text-xs text-ink-2">
        <span data-testid="metric-counts">
          {sla} · {counts}
        </span>{' '}
        <span role="img" aria-label={how} title={how} className="cursor-help" data-testid="metric-info">
          ⓘ
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <Sparkline values={complete.map((week) => pct(week.pct))} width={64} height={20} />
        <span className="text-xs text-ink-3" data-testid="metric-wtd">
          WTD {toDate && toDate.pct !== null ? `${Number(toDate.pct).toFixed(0)}%` : '–'}
        </span>
      </div>
    </div>
  )
}
