import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiSend } from '../api/client'
import { useClock, useMe, useReference, useSyncStatus, type SyncStatus } from '../api/queries'
import { useToast } from '../components/common/Toasts'
import { ErrorState, Skeleton } from '../components/common/States'
import { Section } from '../components/common/Section'
import { TopBar } from '../components/shell/TopBar'
import { dagsterRunUrl } from '../config'
import { formatAge, formatClock, formatDuration, formatRelative } from '../lib/format'
import { READ_ONLY_HINT } from '../lib/roles'

const SYNC_POLL_MS = 5000 // faster than the Overview, so pending → claimed → done is visible within the drain interval

const STATUS_TONE: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700',
  claimed: 'bg-sky-50 text-sky-700',
  done: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}

type Event = SyncStatus['events'][number]

/** Seconds since the response arrived, so ages keep ticking between polls. */
function useElapsed(since: number): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  return Math.max(0, Math.floor((now - since) / 1000))
}

const shortRun = (runId: string | null) => (runId ? runId.slice(0, 8) : '–')

function RunLink({ runId }: { runId: string | null }) {
  if (!runId) return <span className="text-slate-400">–</span>
  return (
    <a
      href={dagsterRunUrl(runId)}
      target="_blank"
      rel="noreferrer"
      title={`Open run ${runId} in Dagster`}
      className="font-mono text-indigo-700 underline decoration-dotted hover:text-indigo-900"
    >
      {shortRun(runId)}
    </a>
  )
}

export function Sync() {
  const status = useSyncStatus(SYNC_POLL_MS)
  const clock = useClock()
  const reference = useReference()
  const me = useMe()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const elapsed = useElapsed(status.dataUpdatedAt)
  const isAdmin = me.data?.role === 'admin'
  const trigger = useMutation({
    mutationFn: () => apiSend('POST', '/sync/trigger', {}),
    onSuccess: async () => {
      notify('Sync requested')
      await queryClient.invalidateQueries({ queryKey: ['sync-status'] })
    },
    onError: (error) => notify(`Could not trigger a sync: ${(error as Error).message}`, 'error'),
  })

  const data = status.data
  const pipeline = data?.pipeline_status
  const tz = reference.data?.site_timezone ?? 'UTC'
  const sources = Object.entries((pipeline?.source_freshness ?? {}) as Record<string, { extracted_at?: string; max_updated_at?: string }>)

  return (
    <>
      <TopBar title="Sync Status" />
      <main className="flex-1 space-y-5 overflow-auto p-6">
        {status.isError && !data ? (
          <ErrorState what="the sync status" error={status.error} onRetry={() => void status.refetch()} />
        ) : null}
        {!data && status.isPending ? <Skeleton label="sync status" height="h-64" /> : null}
        {data ? (
          <>
            <Section
              title="Pipeline"
              aside={
                <button
                  type="button"
                  disabled={!isAdmin || trigger.isPending}
                  title={isAdmin ? 'Queue a sync now' : READ_ONLY_HINT}
                  className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm enabled:hover:border-slate-400 disabled:opacity-40"
                  onClick={() => trigger.mutate()}
                >
                  Trigger sync
                </button>
              }
            >
              <div className="rounded-card border border-slate-200 bg-white p-4 text-[13px]" data-testid="pipeline-card">
                {pipeline ? (
                  <dl className="grid grid-cols-[10rem_1fr] gap-y-1.5">
                    <dt className="text-slate-500">Last run</dt>
                    <dd data-testid="last-run">
                      <RunLink runId={pipeline.last_run_id} /> <span className="text-slate-400">· {pipeline.last_run_id}</span>
                    </dd>
                    <dt className="text-slate-500">Last success</dt>
                    <dd>{formatClock(pipeline.last_success_at, tz)}</dd>
                    <dt className="text-slate-500">Freshness</dt>
                    <dd>
                      {data.freshness_minutes === null ? '–' : `${formatAge(data.freshness_minutes)} old`}
                      {clock.data ? <span className="text-slate-400"> (demo time)</span> : null}
                    </dd>
                    <dt className="text-slate-500">Rows published</dt>
                    <dd>{pipeline.row_count}</dd>
                  </dl>
                ) : (
                  <p className="text-slate-500">No pipeline run has been published yet.</p>
                )}
                {sources.length > 0 ? (
                  <table className="mt-4 w-full text-left" data-testid="source-freshness">
                    <thead className="text-xs text-slate-500 uppercase">
                      <tr>
                        <th className="py-1 font-medium">Source</th>
                        <th className="font-medium">Extracted</th>
                        <th className="font-medium">Newest record</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sources.map(([name, fresh]) => (
                        <tr key={name} className="border-t border-slate-100">
                          <td className="py-1.5 font-medium uppercase">{name}</td>
                          <td>{fresh.extracted_at ? formatClock(fresh.extracted_at, tz) : '–'}</td>
                          <td>{fresh.max_updated_at ? formatClock(fresh.max_updated_at, tz) : '–'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null}
              </div>
            </Section>

            <Section title="Watermarks">
              <table className="w-full rounded-card border border-slate-200 bg-white text-left text-[13px]" data-testid="watermarks">
                <thead className="text-xs text-slate-500 uppercase">
                  <tr>
                    <th className="px-3 py-1.5 font-medium">Object</th>
                    <th className="font-medium">Run</th>
                    <th className="font-medium">Synced</th>
                  </tr>
                </thead>
                <tbody>
                  {data.watermarks.map((mark) => (
                    <tr key={mark.object_name} className="border-t border-slate-100">
                      <td className="px-3 py-1.5 font-mono">{mark.object_name}</td>
                      <td>
                        <RunLink runId={mark.run_id} />
                      </td>
                      <td>{formatRelative(mark.age_seconds + elapsed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>

            <Section title="Sync events (last 50)">
              <table className="w-full rounded-card border border-slate-200 bg-white text-left text-[13px]" data-testid="sync-events">
                <thead className="text-xs text-slate-500 uppercase">
                  <tr>
                    <th className="px-3 py-1.5 font-medium">#</th>
                    <th className="font-medium">Source</th>
                    <th className="font-medium">Status</th>
                    <th className="font-medium">Run</th>
                    <th className="font-medium">Received</th>
                    <th className="font-medium">Duration</th>
                    <th className="font-medium">Rows</th>
                    <th className="font-medium">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {data.events.map((event: Event) => (
                    <tr key={event.id} data-testid="sync-event" data-event-id={event.id} className="border-t border-slate-100">
                      <td className="px-3 py-1.5">{event.id}</td>
                      <td>{event.source}</td>
                      <td>
                        <span data-testid="event-status" className={`rounded-chip px-2 py-0.5 ${STATUS_TONE[event.status] ?? ''}`}>
                          {event.status}
                        </span>
                      </td>
                      <td>
                        <RunLink runId={event.run_id} />
                      </td>
                      <td>{formatRelative(event.age_seconds + elapsed)}</td>
                      <td>{formatDuration(event.duration_ms)}</td>
                      <td>{event.rows_upserted ?? '–'}</td>
                      <td className="max-w-64 truncate text-red-700" title={event.error ?? undefined}>
                        {event.error ?? ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.events.length === 0 ? <p className="text-[13px] text-slate-500">No sync events yet.</p> : null}
            </Section>
          </>
        ) : null}
      </main>
    </>
  )
}
