import type { Metrics } from '../../api/queries'
import { Sparkline } from './Sparkline'

type Metric = Metrics['metrics'][number]

const TONES: Record<string, string> = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  amber: 'border-amber-200 bg-amber-50 text-amber-800',
  red: 'border-red-200 bg-red-50 text-red-800',
}

const pct = (value: string | number | null | undefined): number | null =>
  value === null || value === undefined ? null : Number(value)

/**
 * F10-FR-08. The headline is the last complete week (the week before the final entry, which is the week to
 * date). A metric still waiting for its signal shows a grey "–" with the reason and a Tier 2 tag.
 */
export function MetricChip({ metric }: { metric: Metric }) {
  if (metric.status === 'awaiting_signal') {
    return (
      <div
        data-testid={`metric-${metric.metric_id}`}
        title={metric.null_reason ?? 'Awaiting signal'}
        className="rounded-card border border-slate-200 bg-slate-100 px-3 py-2 text-slate-700"
      >
        <div className="flex items-center justify-between text-xs">
          <span>{metric.metric_id} · {metric.label}</span>
          <span className="rounded-chip bg-slate-200 px-1.5 py-0.5 text-slate-700">Tier 2</span>
        </div>
        <div className="text-xl font-semibold" aria-label={`${metric.label}: no data. ${metric.null_reason ?? ''}`}>–</div>
      </div>
    )
  }
  const weeks = metric.weeks
  const complete = weeks.slice(0, -1)
  const headline = complete[complete.length - 1]
  const toDate = weeks[weeks.length - 1]
  const tone = TONES[headline?.rag ?? ''] ?? 'border-slate-200 bg-slate-50 text-slate-700'
  return (
    <div data-testid={`metric-${metric.metric_id}`} className={`rounded-card border px-3 py-2 ${tone}`}>
      <div className="text-xs">{metric.metric_id} · {metric.label}</div>
      <div className="flex items-baseline gap-2">
        <span className="text-xl font-semibold tabular-nums" data-testid="metric-headline">
          {headline && headline.pct !== null ? `${Number(headline.pct).toFixed(0)}%` : '–'}
        </span>
        <span className="text-xs" data-testid="metric-wtd">
          WTD {toDate && toDate.pct !== null ? `${Number(toDate.pct).toFixed(0)}%` : '–'}
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <Sparkline values={complete.map((week) => pct(week.pct))} />
        {metric.sla_days ? <span className="text-xs whitespace-nowrap">SLA {metric.sla_days} d</span> : null}
      </div>
    </div>
  )
}
