import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { apiSend } from '../../api/client'
import { useMe, useSyncHealth, useSyncStatus, type SyncStatus } from '../../api/queries'
import { HealthCard, type Tone } from '../../components/admin/HealthCard'
import { PageIntro } from '../../components/admin/PageIntro'
import { ConfirmDialog } from '../../components/common/ConfirmDialog'
import { ErrorState, Skeleton } from '../../components/common/States'
import { useToast } from '../../components/common/Toasts'
import { DataTable, type Column } from '../../components/datatable/DataTable'
import { formatDuration, formatRelative } from '../../lib/format'
import { READ_ONLY_HINT } from '../../lib/roles'

const POLL_MS = 3000 // fast enough to see pending → claimed → done within the worker's 2 s wake
const CONFIRM = "This starts real work that affects everyone's view."
const STATUS_TONE: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700',
  claimed: 'bg-sky-50 text-sky-700',
  done: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}
const DRAIN_AMBER_SECONDS = 30
const DRAIN_RED_SECONDS = 120

type Event = SyncStatus['events'][number]
type Action = 'pipeline' | 'drain'

/** Seconds since the response arrived, so wall-clock ages keep ticking between polls. */
function useElapsed(since: number): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  return Math.max(0, Math.floor((now - since) / 1000))
}

/** How long ago an instant of the event happened: its age now, less the time between arrival and that instant. */
const ageAt = (event: Event, iso: string, elapsed: number) =>
  Math.max(0, Math.round(event.age_seconds + elapsed - (Date.parse(iso) - Date.parse(event.received_at)) / 1000))
const age = (seconds: number | null | undefined) => (seconds === null || seconds === undefined ? '—' : formatRelative(seconds))
const countTone = (count: number, nonZero: Tone): Tone => (count === 0 ? 'green' : nonZero)

/** Webhook Sync Status (F21-FR-03 to FR-05): the trigger queue's health, its events and the actions. */
export function WebhookStatus() {
  const health = useSyncHealth(POLL_MS)
  const status = useSyncStatus(POLL_MS)
  const me = useMe()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(new Set())
  const [confirm, setConfirm] = useState<Action | null>(null)
  const elapsed = useElapsed(Math.max(status.dataUpdatedAt, health.dataUpdatedAt))
  const isAdmin = me.data?.role === 'admin'

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['sync-health'] }).then(() => queryClient.invalidateQueries({ queryKey: ['sync-status'] }))
  const run = useMutation({
    mutationFn: (action: Action) => (action === 'pipeline' ? apiSend('POST', '/sync/run-pipeline', {}) : apiSend('POST', '/sync/trigger', {})),
    onSuccess: async (_, action) => {
      notify(action === 'pipeline' ? 'Pipeline run started' : 'Queue drain requested')
      setConfirm(null)
      await refresh()
    },
    onError: (error) => {
      notify(`Could not start it: ${(error as Error).message}`, 'error')
      setConfirm(null)
    },
  })

  const toggle = (id: number) =>
    setExpanded((current) => {
      const next = new Set(current)
      if (!next.delete(id)) next.add(id)
      return next
    })

  const columns = useMemo<Column<Event>[]>(
    () => [
      {
        id: 'expand',
        header: '',
        text: () => '',
        cell: (event) => (
          <button
            type="button"
            aria-label={`${expanded.has(event.id) ? 'Collapse' : 'Expand'} event ${event.id}`}
            aria-expanded={expanded.has(event.id)}
            data-testid="event-expand"
            className="px-1 text-ink-2 hover:text-ink"
            onClick={(click) => {
              click.stopPropagation()
              toggle(event.id)
            }}
          >
            {expanded.has(event.id) ? '▾' : '▸'}
          </button>
        ),
      },
      {
        id: 'received',
        header: 'Received',
        text: (event) => age(event.age_seconds + elapsed),
        sortValue: (event) => event.age_seconds,
        cell: (event) => age(event.age_seconds + elapsed),
      },
      { id: 'source', header: 'Source', text: (event) => event.source, cell: (event) => event.source },
      {
        id: 'run',
        header: 'Run ID',
        text: (event) => (event.run_id ? event.run_id.slice(0, 8) : '—'),
        cell: (event) => (event.run_id ? <span className="font-mono">{event.run_id.slice(0, 8)}</span> : '—'),
      },
      {
        id: 'status',
        header: 'Status',
        text: (event) => event.status,
        cell: (event) => (
          <span data-testid="event-status" className={`rounded-pill px-2 py-0.5 ${STATUS_TONE[event.status] ?? ''}`}>
            {event.status}
          </span>
        ),
      },
      { id: 'attempts', header: 'Attempts', text: (event) => String(event.attempts), sortValue: (event) => event.attempts, cell: (event) => event.attempts },
      {
        id: 'views',
        header: 'Views Synced',
        text: (event) => String(event.objects_synced ?? '—'),
        sortValue: (event) => event.objects_synced ?? -1,
        cell: (event) => event.objects_synced ?? '—',
      },
      {
        id: 'rows',
        header: 'Rows Upserted',
        text: (event) => String(event.rows_upserted ?? '—'),
        sortValue: (event) => event.rows_upserted ?? -1,
        cell: (event) => event.rows_upserted ?? '—',
      },
      {
        id: 'duration',
        header: 'Duration',
        text: (event) => formatDuration(event.duration_ms),
        sortValue: (event) => event.duration_ms ?? -1,
        cell: (event) => formatDuration(event.duration_ms),
      },
    ],
    [expanded, elapsed],
  )

  const h = health.data
  const drainTone: Tone =
    h?.last_drain_age_seconds === null || h?.last_drain_age_seconds === undefined
      ? 'grey'
      : h.last_drain_age_seconds >= DRAIN_RED_SECONDS
        ? 'red'
        : h.last_drain_age_seconds >= DRAIN_AMBER_SECONDS
          ? 'amber'
          : 'green'
  const polled = h?.poll_fallbacks_24h ?? 0
  const adminHint = isAdmin ? undefined : READ_ONLY_HINT
  const button = 'rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm enabled:hover:border-slate-400 disabled:opacity-40'

  return (
    <main className="flex-1 space-y-4 overflow-auto p-6 pb-20" data-testid="webhook-status-page">
      <div className="flex items-start justify-between gap-4">
        <PageIntro
          subtitle="Health of the trigger queue: a pipeline run sends a webhook, the worker drains it and mirrors the data"
          clockNote="Ages on this page are wall-clock time: they count real seconds since the event or the worker's last loop, not the demo clock."
        />
        <div className="flex shrink-0 gap-2">
          <button type="button" className={button} onClick={() => void refresh()}>
            Refresh
          </button>
          <button type="button" disabled={!isAdmin || run.isPending} title={adminHint} className={button} onClick={() => setConfirm('pipeline')}>
            Trigger Sync Now
          </button>
          <button type="button" disabled={!isAdmin || run.isPending} title={adminHint} className={button} onClick={() => setConfirm('drain')}>
            Drain Queue Now
          </button>
        </div>
      </div>

      {health.isError && !h ? <ErrorState what="the queue health" error={health.error} onRetry={() => void health.refetch()} /> : null}
      {!h && health.isPending ? <Skeleton label="queue health" height="h-24" /> : null}
      {h ? (
        <div className="grid grid-cols-6 gap-3" data-testid="health-cards">
          <HealthCard
            testId="card-last-webhook"
            label="Last Webhook Received"
            value={age(h.last_webhook_age_seconds === null ? null : h.last_webhook_age_seconds + elapsed)}
            tone={h.last_webhook_age_seconds === null ? 'grey' : 'green'}
          />
          <HealthCard testId="card-pending" label="Pending Events" value={String(h.pending)} tone={countTone(h.pending, 'amber')} />
          <HealthCard testId="card-error" label="Error Events" value={String(h.error)} tone={countTone(h.error, 'red')} />
          <HealthCard
            testId="card-abandoned"
            label="Abandoned Events"
            value={String(h.abandoned)}
            note={`claimed over ${h.stale_claim_minutes} min, or 2+ attempts`}
            tone={countTone(h.abandoned, 'red')}
          />
          <HealthCard
            testId="card-poll"
            label="Safety-Poll Fallbacks (24h)"
            value={String(polled)}
            tag={h.poll_available ? undefined : 'T2-02'}
            tone={countTone(polled, 'amber')}
          />
          <HealthCard
            testId="card-drain"
            label="Last Drain"
            value={age(h.last_drain_age_seconds === null ? null : h.last_drain_age_seconds + elapsed)}
            note={h.last_drain_age_seconds === null ? 'no worker has reported yet' : undefined}
            tone={drainTone}
          />
        </div>
      ) : null}

      {status.isError && !status.data ? <ErrorState what="the sync events" error={status.error} onRetry={() => void status.refetch()} /> : null}
      {status.data ? (
        <DataTable
          rows={status.data.events}
          columns={columns}
          rowKey={(event) => String(event.id)}
          exportName="sync-events"
          unit={['event', 'events']}
          empty="No sync events yet."
          defaultPageSize={25}
          columnsKey="webhook-status"
          rowTestId="sync-event"
          ariaLabel="Sync events"
          headerFilters={false}
          stickyFirst={false}
          expansion={(event) =>
            expanded.has(event.id) ? (
              <dl className="grid grid-cols-[9rem_1fr] gap-y-1 text-xs" data-testid="event-detail">
                <dt className="text-ink-2">Drain pass</dt>
                <dd className="font-mono">{event.drain_pass_id ?? '—'}</dd>
                <dt className="text-ink-2">Claimed</dt>
                <dd>{event.claimed_at ? formatRelative(ageAt(event, event.claimed_at, elapsed)) : '—'}</dd>
                <dt className="text-ink-2">Finished</dt>
                <dd>{event.finished_at ? formatRelative(ageAt(event, event.finished_at, elapsed)) : '—'}</dd>
                <dt className="text-ink-2">Error</dt>
                <dd className="break-words whitespace-normal text-red-700">{event.error ?? '—'}</dd>
              </dl>
            ) : null
          }
        />
      ) : null}

      {confirm ? (
        <ConfirmDialog
          title={confirm === 'pipeline' ? 'Trigger Sync Now' : 'Drain Queue Now'}
          message={`${confirm === 'pipeline' ? 'Starts a pipeline run; its webhook then flows through the queue as usual.' : 'Queues a manual sync event for the worker to drain.'} ${CONFIRM}`}
          confirmLabel={confirm === 'pipeline' ? 'Start the run' : 'Drain now'}
          busy={run.isPending}
          onConfirm={() => run.mutate(confirm)}
          onCancel={() => setConfirm(null)}
        />
      ) : null}
    </main>
  )
}
