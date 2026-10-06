import { Brush, CartesianGrid, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useReport } from '../../api/queries'
import { ErrorState, Skeleton } from '../../components/common/States'
import { ACCENT, HAIRLINE, INK_2 } from '../../lib/chartColours'
import { dayLabel, weekLabel, type ReleaseRateReport } from '../../lib/reports'

/** Lots released per ISO week, with the weekly target as a dashed line and a range scrubber. */
export function ReleaseRate({ params }: { params: URLSearchParams }) {
  const report = useReport<ReleaseRateReport>('release-rate', params)
  if (report.isError) return <ErrorState what="the release rate" error={report.error} onRetry={() => void report.refetch()} />
  const data = report.data
  if (!data) return <Skeleton label="the release rate" height="h-80" />
  const points = data.weeks.map((week) => ({
    label: `${weekLabel(week.week_start)} · ${dayLabel(week.week_start)}`,
    released: week.released_count,
  }))
  return (
    <div className="rounded-card border border-hairline bg-white p-4" data-testid="report-release-rate">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-ink-2 uppercase">Lots released per week · {data.year}</h2>
        <span className="text-xs text-ink-2">Dashed line: {data.weekly_target} a week · the current week to date is not shown</span>
      </div>
      {points.length === 0 ? (
        <p className="py-10 text-center text-ink-2">No releases in {data.year}.</p>
      ) : (
        <div className="h-80" data-testid="release-chart">
          <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
            <LineChart data={points} margin={{ top: 24, right: 24, bottom: 8, left: 0 }}>
              <CartesianGrid vertical={false} stroke={HAIRLINE} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: INK_2 }} minTickGap={40} tickFormatter={(value: string) => value.split(' · ')[0]!} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: INK_2 }} />
              <Tooltip />
              <ReferenceLine y={data.weekly_target} stroke="#111827" strokeDasharray="6 4" />
              <Line type="monotone" dataKey="released" name="Released" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false}>
                <LabelList dataKey="released" position="top" style={{ fontSize: 11 }} />
              </Line>
              <Brush dataKey="label" height={24} stroke={INK_2} tickFormatter={(value: string) => value.split(' · ')[0]!} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
