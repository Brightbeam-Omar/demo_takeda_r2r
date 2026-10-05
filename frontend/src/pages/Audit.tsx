import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { apiGet, type Schemas } from '../api/client'
import { useReference, useUsers } from '../api/queries'
import { AuditDetails } from '../components/audit/AuditDetails'
import { EmptyState, ErrorState, Skeleton } from '../components/common/States'
import { formatClock, humanize } from '../lib/format'
import { usePersona } from '../state/persona'

type Page = Schemas['AuditPage']

const PAGE_SIZE = 50
/** The audit action vocabulary (OQ-058). Agent actions arrive with F12. */
const ACTIONS = ['need_by_set', 'need_by_cleared', 'expedite_set', 'expedite_cleared', 'status_set', 'status_cleared', 'comment_added', 'forbidden']

const field = 'rounded-chip border border-slate-300 bg-white px-2 py-1.5 text-sm'

export function Audit() {
  const [actor, setActor] = useState('')
  const [action, setAction] = useState('')
  const [rowKey, setRowKey] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState<ReadonlySet<number>>(new Set())
  const persona = usePersona()
  const users = useUsers()
  const reference = useReference()
  const tz = reference.data?.site_timezone ?? 'UTC'

  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
  if (actor) params.set('actor', actor)
  if (action) params.set('action', action)
  if (rowKey.trim()) params.set('row_key', rowKey.trim())
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  const invalidRange = Boolean(from && to && to < from)
  const audit = useQuery({
    queryKey: ['audit', params.toString(), persona],
    queryFn: () => apiGet<Page>('/audit', params),
    placeholderData: keepPreviousData,
    enabled: !invalidRange,
    refetchInterval: 10_000,
  })

  // Changing a filter returns to the first page.
  const filter = <T,>(set: (value: T) => void) => (value: T) => {
    set(value)
    setOffset(0)
  }
  const toggle = (id: number) =>
    setOpen((current) => {
      const next = new Set(current)
      if (!next.delete(id)) next.add(id)
      return next
    })
  const data = audit.data
  const anyFilter = Boolean(actor || action || rowKey || from || to)

  return (
    <>
      <main className="flex-1 space-y-4 overflow-auto p-6">
        <section aria-label="Filters" className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-500">
            Actor
            {users.data ? (
              <select aria-label="Actor" className={`${field} mt-1 block`} value={actor} onChange={(e) => filter(setActor)(e.target.value)}>
                <option value="">Anyone</option>
                {users.data.map((user) => (
                  <option key={user.user_key} value={user.user_key}>
                    {user.display_name}
                  </option>
                ))}
                <option value="system">System</option>
              </select>
            ) : (
              <input aria-label="Actor" className={`${field} mt-1 block`} value={actor} onChange={(e) => filter(setActor)(e.target.value)} />
            )}
          </label>
          <label className="text-xs text-slate-500">
            Action
            <select aria-label="Action" className={`${field} mt-1 block`} value={action} onChange={(e) => filter(setAction)(e.target.value)}>
              <option value="">Any action</option>
              {ACTIONS.map((name) => (
                <option key={name} value={name}>
                  {humanize(name)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-500">
            Batch row
            <input
              aria-label="Row"
              placeholder="RM10031|B2077|…"
              className={`${field} mt-1 block w-56`}
              value={rowKey}
              onChange={(e) => filter(setRowKey)(e.target.value)}
            />
          </label>
          <label className="text-xs text-slate-500">
            From
            <input type="date" aria-label="From" className={`${field} mt-1 block`} value={from} onChange={(e) => filter(setFrom)(e.target.value)} />
          </label>
          <label className="text-xs text-slate-500">
            To
            <input type="date" aria-label="To" className={`${field} mt-1 block`} value={to} onChange={(e) => filter(setTo)(e.target.value)} />
          </label>
          {anyFilter ? (
            <button
              type="button"
              className="pb-2 text-sm text-indigo-600 underline hover:text-indigo-800"
              onClick={() => {
                setActor('')
                setAction('')
                setRowKey('')
                setFrom('')
                setTo('')
                setOffset(0)
              }}
            >
              Clear all
            </button>
          ) : null}
        </section>
        {invalidRange ? (
          <p role="alert" className="text-sm text-red-700">
            "To" is before "From".
          </p>
        ) : null}
        {audit.isError && !data ? <ErrorState what="the audit log" error={audit.error} onRetry={() => void audit.refetch()} /> : null}
        {!data && audit.isPending && !invalidRange ? <Skeleton label="audit log" height="h-64" /> : null}
        {data && data.items.length === 0 ? (
          <EmptyState>{anyFilter ? 'No audit entries match these filters.' : 'No audit entries yet.'}</EmptyState>
        ) : null}
        {data && data.items.length > 0 ? (
          <>
            <table className="w-full rounded-card border border-slate-200 bg-white text-left text-[13px]" data-testid="audit-table">
              <thead className="text-xs text-slate-500 uppercase">
                <tr>
                  <th className="w-8 px-2 py-1.5" />
                  <th className="font-medium">When (demo time)</th>
                  <th className="font-medium">Actor</th>
                  <th className="font-medium">Action</th>
                  <th className="font-medium">Batch row</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((entry) => {
                  const expanded = open.has(entry.id)
                  return (
                    <Fragment key={entry.id}>
                      <tr data-testid="audit-entry" data-action={entry.action} className="border-t border-slate-100">
                        <td className="px-2 py-1.5">
                          <button
                            type="button"
                            aria-expanded={expanded}
                            aria-label={`${expanded ? 'Hide' : 'Show'} details of entry ${entry.id}`}
                            className="rounded-chip px-1.5 text-slate-500 hover:bg-slate-100"
                            onClick={() => toggle(entry.id)}
                          >
                            {expanded ? '▾' : '▸'}
                          </button>
                        </td>
                        <td>{formatClock(entry.at, tz)}</td>
                        <td>{entry.actor_user_key ?? 'system'}</td>
                        <td>{humanize(entry.action)}</td>
                        <td className="font-mono text-xs">{entry.row_key ?? '–'}</td>
                      </tr>
                      {expanded ? (
                        <tr className="bg-slate-50">
                          <td />
                          <td colSpan={4} className="py-2 pr-3">
                            <AuditDetails details={entry.details as Record<string, unknown> | null} />
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
            <div className="flex items-center justify-between text-sm text-slate-600">
              <span data-testid="audit-count">
                {offset + 1}–{offset + data.items.length} of {data.total}
              </span>
              <div className="flex gap-2">
                <button type="button" disabled={offset === 0} className="rounded-chip border border-slate-300 px-3 py-1 enabled:hover:bg-slate-50 disabled:opacity-40" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                  Previous
                </button>
                <button type="button" disabled={offset + PAGE_SIZE >= data.total} className="rounded-chip border border-slate-300 px-3 py-1 enabled:hover:bg-slate-50 disabled:opacity-40" onClick={() => setOffset(offset + PAGE_SIZE)}>
                  Next
                </button>
              </div>
            </div>
          </>
        ) : null}
      </main>
    </>
  )
}
