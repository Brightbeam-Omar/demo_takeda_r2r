import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useReport } from '../../api/queries'
import { ErrorState, Skeleton } from '../../components/common/States'
import { HAIRLINE, INK_2, RAG_HEX } from '../../lib/chartColours'
import { formatPct, weekLabel, type AdherenceReport } from '../../lib/reports'

/** Released lots per week, split into within and exceeded needs-by (F20 layout). */
export function Adherence({ params }: { params: URLSearchParams }) {
  const report = useReport<AdherenceReport>('adherence', params)
  if (report.isError) return <ErrorState what="adherence" error={report.error} onRetry={() => void report.refetch()} />
  const data = report.data
  if (!data) return <Skeleton label="adherence" height="h-80" />
  const points = data.weeks.map((week) => ({
    label: weekLabel(week.week_start),
    within: week.within,
    exceeded: week.exceeded,
  }))
  const { adherence } = data
  return (
    <div className="rounded-card border border-hairline bg-white p-4" data-testid="report-adherence">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-ink-2 uppercase">Released lots by week · {data.year}</h2>
        <span className="text-xs text-ink-2" data-testid="adherence-summary">
          {formatPct(adherence.pct)} within needs-by ({adherence.on_time} / {adherence.on_time + adherence.late}), target {adherence.target_pct}%
        </span>
      </div>
      {points.length === 0 ? (
        <p className="py-10 text-center text-ink-2">No released lots with a need-by in {data.year}.</p>
      ) : (
        <div className="h-80" data-testid="adherence-chart">
          <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
            <BarChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid vertical={false} stroke={HAIRLINE} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: INK_2 }} minTickGap={24} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: INK_2 }} />
              <Tooltip />
              <Legend itemSorter={null} />
              <Bar dataKey="within" name="Within needs-by" stackId="nbd" fill={RAG_HEX.green} isAnimationActive={false} />
              <Bar dataKey="exceeded" name="Exceeded needs-by" stackId="nbd" fill={RAG_HEX.red} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {adherence.excluded > 0 && (
        <p className="mt-2 text-xs text-ink-2">{adherence.excluded} released lots without a need-by are not counted.</p>
      )}
    </div>
  )
}
