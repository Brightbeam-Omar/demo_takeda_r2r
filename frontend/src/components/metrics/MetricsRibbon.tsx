import type { Metrics } from '../../api/queries'
import { isoWeek } from '../../lib/calendar'
import { MetricCard } from './MetricCard'

type Metric = Metrics['metrics'][number]

/** The last complete week as published (`week_start` of the headline), formatted `Week 41 (2026)`. */
export function weekLabel(metrics: Metric[]): string | null {
  for (const metric of metrics) {
    const complete = metric.weeks.slice(0, -1)
    const last = complete[complete.length - 1]
    if (last) {
      const { week, year } = isoWeek(last.week_start)
      return `Week ${week} (${year})`
    }
  }
  return null
}

export const metricsTitle = (metrics: Metric[]) =>
  `${weekLabel(metrics) ?? 'Latest week'} — ${metrics.length} R2R Metrics`

interface Props {
  metrics: Metric[]
  stageLabels?: Record<string, string>
}

export function MetricsRibbon({ metrics, stageLabels = {} }: Props) {
  return (
    <div className="grid grid-cols-7 gap-2" data-testid="metrics-ribbon">
      {metrics.map((metric) => (
        <MetricCard key={metric.metric_id} metric={metric} stageLabel={metric.stage_key ? stageLabels[metric.stage_key] : undefined} />
      ))}
    </div>
  )
}
