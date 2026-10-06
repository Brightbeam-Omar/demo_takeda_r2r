import { useState } from 'react'
import { Bar, BarChart, Brush, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useReport } from '../../api/queries'
import { ErrorState, Skeleton } from '../../components/common/States'
import { HAIRLINE, INK_2, stageHex } from '../../lib/chartColours'
import { dayLabel, formatPct, monthLabel, trendView, weekLabel, type TrendsReport } from '../../lib/reports'

type Grain = 'weekly' | 'monthly'
type StageGrain = 'daily' | 'weekly'

/** The scrubber opens on the last 8 weeks; the whole history stays reachable (F20 review). */
const DEFAULT_WEEKS = 8
const DEFAULT_DAYS = DEFAULT_WEEKS * 7

const GRAINS: [Grain, string][] = [['weekly', 'Weekly'], ['monthly', 'Monthly']]
const STAGE_GRAINS: [StageGrain, string][] = [['daily', 'Daily'], ['weekly', 'Weekly']]

const TREND_TONE = { up: 'text-green-700', down: 'text-red-700', stable: 'text-ink-2', none: 'text-ink-3' }

function Toggle<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex overflow-hidden rounded-chip border border-hairline">
      {options.map(([key, text]) => (
        <button
          key={key}
          type="button"
          aria-pressed={value === key}
          className={`px-3 py-1 text-sm ${value === key ? 'bg-accent-tint font-semibold text-accent' : 'bg-white text-ink-2 hover:bg-panel'}`}
          onClick={() => onChange(key)}
        >
          {text}
        </button>
      ))}
    </div>
  )
}

/** SLA Trends table, then Pipeline Stage Trends (F20 layout). */
export function Trends({ params }: { params: URLSearchParams }) {
  const [grain, setGrain] = useState<Grain>('weekly')
  const [stageGrain, setStageGrain] = useState<StageGrain>('daily')
  const query = new URLSearchParams(params)
  query.set('grain', grain)
  query.set('stage_grain', stageGrain)
  const report = useReport<TrendsReport>('trends', query)
  if (report.isError) return <ErrorState what="the trends" error={report.error} onRetry={() => void report.refetch()} />
  const data = report.data
  if (!data) return <Skeleton label="the trends" height="h-96" />
  const periodLabel = (iso: string) => (grain === 'weekly' ? weekLabel(iso) : monthLabel(iso))
  const current = data.periods[data.periods.length - 1]
  const points = data.points.map((point) => ({
    label: stageGrain === 'daily' ? dayLabel(point.day) : weekLabel(point.week_start ?? point.day),
    day: point.day,
    ...point.counts,
  }))
  return (
    <div className="space-y-6" data-testid="report-trends">
      <section className="rounded-card border border-hairline bg-white p-4" aria-label="SLA Trends">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-wide text-ink-2 uppercase">SLA Trends</h2>
          <Toggle<Grain> label="SLA trend grain" value={grain} onChange={setGrain} options={GRAINS} />
        </div>
        <table className="w-full text-sm" data-testid="trend-table">
          <thead>
            <tr className="border-b border-hairline text-left text-[11px] tracking-wider text-ink-2 uppercase">
              <th className="py-2 pr-3 font-semibold">Metric</th>
              {data.periods.map((period) => (
                <th key={period} className="px-2 py-2 text-right font-semibold">
                  {periodLabel(period)}
                  {period === current && <span className="block text-[10px] font-normal normal-case">to date</span>}
                </th>
              ))}
              <th className="py-2 pl-3 text-right font-semibold">Trend</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => {
              const trend = trendView(row.trend, row.trend_delta_pp)
              const na = row.status === 'awaiting_signal'
              return (
                <tr key={row.metric_id} data-testid={`trend-row-${row.metric_id}`} className="border-b border-hairline last:border-0">
                  <td className="py-2 pr-3">
                    <span className="font-medium">{row.metric_id}</span> <span className="text-ink-2">{row.label}</span>
                  </td>
                  {row.cells.map((cell) => (
                    <td
                      key={cell.period_start}
                      data-rag={cell.rag ?? undefined}
                      title={na ? (row.null_reason ?? 'N/A') : `${cell.completed} completed`}
                      className={`px-2 py-2 text-right tabular-nums ${cell.rag === 'green' ? 'bg-green-50 text-green-800' : cell.rag ? 'bg-red-50 text-red-800' : 'text-ink-3'}`}
                    >
                      {na ? 'N/A' : formatPct(cell.pct, 0)}
                    </td>
                  ))}
                  <td className={`py-2 pl-3 text-right font-medium ${TREND_TONE[trend.tone]}`} data-testid={`trend-${row.metric_id}`}>
                    {na ? '—' : trend.text}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-ink-2">Trend compares the last complete {grain === 'weekly' ? 'week' : 'month'} with the one before (percentage points; under 2 pp is Stable).</p>
      </section>
      <section className="rounded-card border border-hairline bg-white p-4" aria-label="Pipeline Stage Trends">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-wide text-ink-2 uppercase">Pipeline Stage Trends</h2>
          <Toggle<StageGrain> label="Stage trend grain" value={stageGrain} onChange={setStageGrain} options={STAGE_GRAINS} />
        </div>
        <div className="h-72" data-testid="stage-chart">
          <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
            <BarChart data={points} barCategoryGap={stageGrain === 'daily' ? 0 : '20%'} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid vertical={false} stroke={HAIRLINE} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: INK_2 }} minTickGap={32} />
              <YAxis tick={{ fontSize: 12, fill: INK_2 }} />
              <Tooltip />
              <Legend itemSorter={null} />
              {data.stages.map((stage) => (
                <Bar key={stage.stage_key} dataKey={stage.stage_key} name={stage.label} stackId="open" fill={stageHex(stage.sort)} isAnimationActive={false} />
              ))}
              <Brush key={stageGrain} dataKey="label" height={24} stroke={INK_2} startIndex={Math.max(0, points.length - (stageGrain === 'daily' ? DEFAULT_DAYS : DEFAULT_WEEKS))} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  )
}
