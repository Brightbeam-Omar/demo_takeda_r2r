import type { Metrics } from '../../api/queries'
import { MetricChip } from './MetricChip'

export function MetricsRibbon({ metrics }: { metrics: Metrics['metrics'] }) {
  return (
    <div className="grid grid-cols-7 gap-2" data-testid="metrics-ribbon">
      {metrics.map((metric) => (
        <MetricChip key={metric.metric_id} metric={metric} />
      ))}
    </div>
  )
}
