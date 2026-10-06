import { Link } from 'react-router-dom'
import { useTeams } from '../../api/queries'
import { PageIntro } from '../../components/admin/PageIntro'
import { ErrorState, Skeleton } from '../../components/common/States'

const overviewLink = (stageKeys: string[]) => `/overview?${stageKeys.map((key) => `stage=${encodeURIComponent(key)}`).join('&')}`
const percent = (value: number | null) => (value === null ? '—' : `${value.toFixed(1)}%`)

/** Team Dashboard (F21-FR-06): the open work of each owning team, a snapshot that ignores the filters. */
export function TeamDashboard() {
  const teams = useTeams()
  const data = teams.data
  return (
    <main className="flex-1 space-y-3 overflow-auto p-6 pb-20" data-testid="team-dashboard-page">
      <PageIntro subtitle="Open work by owning team — a snapshot of every lot in flight, whatever the Overview filters say" />
      {teams.isError && !data ? <ErrorState what="the team dashboard" error={teams.error} onRetry={() => void teams.refetch()} /> : null}
      {!data && teams.isPending ? <Skeleton label="team dashboard" height="h-48" /> : null}
      {data ? (
        <table className="w-full rounded-card border border-hairline bg-white text-left text-[13px]" data-testid="team-table">
          <thead className="text-[11px] tracking-wider text-ink-2 uppercase">
            <tr>
              <th className="px-3 py-2 font-semibold">Team</th>
              <th className="font-semibold">Stages</th>
              <th className="text-right font-semibold">Open</th>
              <th className="text-right font-semibold">Late</th>
              <th className="text-right font-semibold">Oldest late</th>
              <th className="text-right font-semibold">At risk</th>
              <th className="px-3 font-semibold" />
            </tr>
          </thead>
          <tbody>
            {data.teams.map((team) => (
              <tr key={team.team} data-testid="team-row" data-team={team.team} className="border-t border-hairline">
                <td className="px-3 py-2 font-medium text-ink">{team.team}</td>
                <td className="text-ink-2">{team.stage_labels.join(', ')}</td>
                <td className="text-right" data-testid="team-open">
                  {team.open}
                </td>
                <td className={`text-right ${team.late > 0 ? 'font-semibold text-red-700' : ''}`} data-testid="team-late">
                  {team.late}
                </td>
                <td className="text-right" data-testid="team-oldest">
                  {team.oldest_late_days === null ? '—' : `${team.oldest_late_days}d over`}
                </td>
                <td className={`text-right ${team.amber > 0 ? 'text-amber-700' : ''}`} data-testid="team-risk">
                  {team.amber} · {percent(team.at_risk_pct)}
                </td>
                <td className="px-3 text-right">
                  <Link className="text-accent hover:underline" to={overviewLink(team.stage_keys)} aria-label={`View ${team.team} in the Overview`}>
                    View in Overview →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-hairline bg-panel font-semibold" data-testid="team-totals">
              <td className="px-3 py-2">All teams</td>
              <td />
              <td className="text-right">{data.totals.open}</td>
              <td className="text-right" data-testid="team-total-late">
                {data.totals.late}
              </td>
              <td />
              <td className="text-right">{data.totals.amber}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      ) : null}
    </main>
  )
}
