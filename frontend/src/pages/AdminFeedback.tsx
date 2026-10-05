import { useQuery } from '@tanstack/react-query'
import { apiGet, type Schemas } from '../api/client'
import { useMe, useReference } from '../api/queries'
import { EmptyState, ErrorState, Skeleton } from '../components/common/States'
import { formatTopBarClock } from '../lib/format'
import { usePersona } from '../state/persona'

type Entry = Schemas['FeedbackOut']

/** F15-FR-06: the feedback list, newest first. Admin only; other roles see why they cannot. */
export function AdminFeedback() {
  const me = useMe()
  const persona = usePersona()
  const reference = useReference()
  const isAdmin = me.data?.role === 'admin'
  const feedback = useQuery({
    queryKey: ['feedback', persona],
    queryFn: () => apiGet<Entry[]>('/feedback'),
    enabled: isAdmin,
    refetchInterval: 10_000,
  })
  const tz = reference.data?.site_timezone ?? 'UTC'

  return (
    <main className="flex-1 overflow-auto p-6" data-testid="feedback-page">
      {!me.data ? (
        <Skeleton label="feedback" />
      ) : !isAdmin ? (
        <EmptyState>Feedback is visible to the Admin role only.</EmptyState>
      ) : feedback.isError ? (
        <ErrorState what="the feedback" error={feedback.error} onRetry={() => void feedback.refetch()} />
      ) : !feedback.data ? (
        <Skeleton label="feedback" />
      ) : feedback.data.length === 0 ? (
        <EmptyState>No feedback yet.</EmptyState>
      ) : (
        <table className="w-full text-left text-[13px]">
          <thead className="text-[11px] uppercase tracking-wider text-ink-2">
            <tr>
              <th className="py-2 pr-4">When</th>
              <th className="py-2 pr-4">User</th>
              <th className="py-2 pr-4">Page</th>
              <th className="py-2">Message</th>
            </tr>
          </thead>
          <tbody>
            {feedback.data.map((entry) => (
              <tr key={entry.id} className="border-t border-hairline align-top" data-testid="feedback-row">
                <td className="py-2 pr-4 whitespace-nowrap tabular-nums">{formatTopBarClock(entry.at, tz)}</td>
                <td className="py-2 pr-4">{entry.user_key}</td>
                <td className="py-2 pr-4 font-mono text-xs">{entry.page}</td>
                <td className="py-2 whitespace-pre-wrap">{entry.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}
