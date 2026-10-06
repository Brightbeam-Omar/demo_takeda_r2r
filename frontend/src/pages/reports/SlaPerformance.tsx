import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { useReport } from '../../api/queries'
import { ErrorState, Skeleton } from '../../components/common/States'
import { HAIRLINE, INK_2, RAG_HEX } from '../../lib/chartColours'
import { isoWeek, type SlaReport } from '../../lib/reports'

/** One vertical bar per metric: the last complete week's on-time %, with the green threshold as a dashed line. */
export function SlaPerformance({ params }: { params: URLSearchParams }) {
  const report = useReport<SlaReport>('sla', params)
  if (report.isError) return <ErrorState what="SLA performance" error={report.error} onRetry={() => void report.refetch()} />
  const data = report.data
  if (!data) return <Skeleton label="SLA performance" height="h-80" />
  const week = data.bars.find((bar) => bar.week_start)?.week_start
  const bars = data.bars.map((bar) => ({
    id: bar.metric_id,
    name: `${bar.metric_id}: ${bar.label.replace(/ On-Time$/, '')}`,
    pct: bar.pct === null ? null : Number(bar.pct),
    rag: bar.rag ?? 'grey',
    counts: `${bar.on_time}/${bar.completed}`,
  }))
  const unavailable = data.bars.filter((bar) => bar.status === 'awaiting_signal')
  return (
    <div className="rounded-card border border-hairline bg-white p-4" data-testid="report-sla">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-ink-2 uppercase">
          On-time % · last complete week{week ? ` (week ${isoWeek(week)})` : ''}
        </h2>
        <span className="text-xs text-ink-2">Dashed line: {data.target_pct}% target</span>
      </div>
      <div className="h-80" data-testid="sla-chart">
        <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
          <BarChart data={bars} margin={{ top: 24, right: 48, bottom: 8, left: 0 }}>
            <CartesianGrid vertical={false} stroke={HAIRLINE} />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: INK_2 }} interval={0} />
            <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12, fill: INK_2 }} />
            <ReferenceLine y={data.target_pct} stroke="#111827" strokeDasharray="6 4" label={{ value: `${data.target_pct}%`, position: 'right', fontSize: 12 }} />
            <Bar dataKey="pct" maxBarSize={72} isAnimationActive={false}>
              {bars.map((bar) => (
                <Cell key={bar.id} fill={RAG_HEX[bar.rag]} />
              ))}
              <LabelList dataKey="pct" position="top" formatter={(value) => (value === null || value === undefined ? 'N/A' : `${Number(value).toFixed(0)}%`)} style={{ fontSize: 13, fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {unavailable.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-ink-2" data-testid="sla-na">
          {unavailable.map((bar) => (
            <li key={bar.metric_id}>
              <span className="font-semibold">{bar.metric_id}: N/A</span> — {bar.null_reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
