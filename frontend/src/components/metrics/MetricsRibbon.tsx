import type { Metrics } from '../../api/queries'
import { MetricChip } from './MetricChip'

export function MetricsRibbon({ metrics }: { metrics: Metrics['metrics'] }) {
  return (
    <div className="flex items-start gap-2" data-testid="metrics-ribbon">
      {metrics.map((metric) => (
        <MetricChip key={metric.metric_id} metric={metric} />
      ))}
    </div>
  )
}
