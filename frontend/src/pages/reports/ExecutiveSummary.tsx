import { useReport } from '../../api/queries'
import { ProgressCard } from '../../components/charts/ProgressCard'
import { ErrorState, Skeleton } from '../../components/common/States'
import { fillPercent, formatPct, markerPercent, type Summary } from '../../lib/reports'

/** Three year-to-date cards: Release Rate, Needs-by Adherence and Expedite On-Time Rate (F20 layout). */
export function ExecutiveSummary({ params }: { params: URLSearchParams }) {
  const report = useReport<Summary>('summary', params)
  if (report.isError) return <ErrorState what="the summary" error={report.error} onRetry={() => void report.refetch()} />
  const data = report.data
  if (!data) return <Skeleton label="the summary" height="h-48" />
  const { release, adherence, expedite } = data
  return (
    <div className="grid grid-cols-3 gap-4" data-testid="report-summary">
      <ProgressCard
        testId="card-release"
        title={`Release Rate · ${data.year} to date`}
        figure={`${release.released} / ${release.annual_target}`}
        fill={fillPercent(release.released, release.annual_target)}
        marker={markerPercent(release.prorata_target, release.annual_target)}
        markerLabel={`Pro-rata target ${release.prorata_target}`}
        rag={release.pct_of_prorata === null ? null : release.pct_of_prorata >= 100 ? 'green' : release.pct_of_prorata >= 90 ? 'amber' : 'red'}
        counts={
          <>
            {release.pct_of_prorata === null ? '–' : `${release.pct_of_prorata}%`} of pro-rata target
          </>
        }
        note={`Pro-rata target ${release.prorata_target} over ${release.coverage_weeks} coverage weeks of the ${release.annual_target} a year.`}
      />
      <ProgressCard
        testId="card-adherence"
        title="Needs-by Adherence"
        figure={formatPct(adherence.pct)}
        fill={adherence.pct === null ? 0 : Number(adherence.pct)}
        marker={adherence.target_pct}
        markerLabel={`Target ${adherence.target_pct}%`}
        rag={adherence.rag}
        counts={
          <>
            {adherence.on_time} on-time / {adherence.late} late
          </>
        }
        note={
          adherence.excluded > 0
            ? `Target ${adherence.target_pct}%. ${adherence.excluded} released lots without a need-by are not counted.`
            : `Target ${adherence.target_pct}%.`
        }
      />
      <ProgressCard
        testId="card-expedite"
        title="Expedite On-Time Rate"
        figure={formatPct(expedite.pct)}
        fill={expedite.pct === null ? 0 : Number(expedite.pct)}
        marker={expedite.target_pct}
        markerLabel={`Target ${expedite.target_pct}%`}
        rag={expedite.rag}
        counts={
          <>
            {expedite.on_time} on-time / {expedite.expedited} expedited
          </>
        }
        note={
          <>
            Tracked separately from the standard M1–M7 metrics — a missed expedite does not penalise the standard SLA.
            {expedite.app_only > 0 && ` ${expedite.app_only} more expedited in the app only (no due date, not in the rate).`}
          </>
        }
      />
    </div>
  )
}
