import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiSend } from '../../api/client'
import { useMe, useReference, type RowDetail } from '../../api/queries'
import { formatTopBarClock } from '../../lib/format'
import { READ_ONLY_HINT, canLogStatus } from '../../lib/roles'
import { markSaved } from '../../state/just-saved'
import { useToast } from '../common/Toasts'
import { Dot } from '../overview/cells'
import { BatchWindowShell } from './BatchWindowShell'

interface Props {
  rowKey: string
  onClose: () => void
}

type Entry = RowDetail['status_log'][number]
type Tab = 'latest' | 'history'

/** W4 Status Log (F19): the latest entry, the history and the form that adds an update (F19-FR-05). */
export function StatusLogWindow({ rowKey, onClose }: Props) {
  return (
    <BatchWindowShell
      rowKey={rowKey}
      onClose={onClose}
      testId="status-window"
      title={(detail) => `Status Log — ${detail.batch_no}`}
      description={null}
    >
      {(detail) => <StatusLogBody detail={detail} onClose={onClose} />}
    </BatchWindowShell>
  )
}

function EntryCard({ entry }: { entry: Entry }) {
  const reference = useReference()
  const option = reference.data?.status_options.find((o) => o.key === entry.status)
  const reason = reference.data?.status_reasons.find((r) => r.key === entry.reason_code)
  const timezone = reference.data?.site_timezone ?? 'Europe/Dublin'
  return (
    <li className="rounded-card border border-slate-200 p-3 text-[13px]" data-testid="status-entry">
      <div className="flex flex-wrap items-center gap-2">
        {entry.status ? (
          <span className="inline-flex items-center gap-1.5 font-semibold" data-testid="status-entry-status">
            <Dot colour={option?.colour ?? 'grey'} what="Status" />
            {option?.label ?? entry.status}
          </span>
        ) : (
          <span className="text-slate-500">Comment</span>
        )}
        {entry.team && <span className="text-slate-600">· {entry.team}</span>}
        <span className="ml-auto text-xs text-slate-500">
          {entry.author_user_key} · {formatTopBarClock(entry.at, timezone)}
        </span>
      </div>
      {reason && <p className="mt-1 text-slate-600 italic">{reason.label}</p>}
      <p className="mt-1 whitespace-pre-wrap" data-testid="status-entry-comment">
        {entry.comment}
      </p>
    </li>
  )
}

function StatusLogBody({ detail, onClose }: { detail: RowDetail; onClose: () => void }) {
  const me = useMe()
  const reference = useReference()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [tab, setTab] = useState<Tab>('latest')
  const [newestFirst, setNewestFirst] = useState(true)
  const [status, setStatus] = useState('on_track')
  const [team, setTeam] = useState('')
  const [reason, setReason] = useState('')
  const [comment, setComment] = useState('')
  const allowed = canLogStatus(me.data?.role)
  const hint = allowed ? undefined : READ_ONLY_HINT
  const log = detail.status_log // newest first
  const ordered = newestFirst ? log : [...log].reverse()
  const teams = [...new Set((reference.data?.stages ?? []).map((stage) => String(stage.team)).filter(Boolean))]

  const add = useMutation({
    mutationFn: () =>
      apiSend('POST', `/rows/${encodeURIComponent(detail.row_key)}/status-log`, {
        status,
        team: team || null,
        reason_code: reason || null,
        comment: comment.trim(),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries()
      markSaved(detail.row_key)
      notify('Status update added')
      setComment('')
      setReason('')
      setTab('latest')
    },
  })

  return (
    <div className="space-y-3">
      <p className="text-[13px] text-slate-700" data-testid="status-subtitle">
        {detail.material_no} · {detail.stage_label}
      </p>
      <div role="tablist" aria-label="Status log" className="flex gap-1 border-b border-slate-200">
        {(['latest', ...(log.length > 1 ? (['history'] as const) : [])] as Tab[]).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`-mb-px border-b-2 px-3 py-1.5 text-[13px] font-medium ${tab === id ? 'border-accent text-accent' : 'border-transparent text-slate-600 hover:text-slate-900'}`}
            onClick={() => setTab(id)}
          >
            {id === 'latest' ? 'Latest' : `History (${log.length})`}
          </button>
        ))}
      </div>
      {tab === 'history' && log.length > 1 ? (
        <>
          <button type="button" className="text-xs text-accent hover:underline" onClick={() => setNewestFirst(!newestFirst)}>
            {newestFirst ? 'Newest first ▾' : 'Oldest first ▴'}
          </button>
          <ul className="space-y-2" data-testid="status-history">
            {ordered.map((entry) => (
              <EntryCard key={entry.id} entry={entry} />
            ))}
          </ul>
        </>
      ) : log.length > 0 ? (
        <ul className="space-y-2" data-testid="status-latest">
          <EntryCard entry={log[0]!} />
        </ul>
      ) : (
        <p className="text-[13px] text-slate-500">No status updates yet.</p>
      )}

      <form
        className="space-y-2 border-t border-slate-200 pt-3 text-[13px]"
        aria-label="Add a status update"
        title={hint}
        onSubmit={(event) => {
          event.preventDefault()
          if (comment.trim()) add.mutate()
        }}
      >
        <div className="grid grid-cols-3 gap-2">
          <label>
            <span className="mb-1 block text-slate-500">Status</span>
            <select
              aria-label="Status"
              disabled={!allowed}
              className="w-full rounded-chip border border-slate-300 px-2 py-1.5 disabled:opacity-50"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              {(reference.data?.status_options ?? []).map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="mb-1 block text-slate-500">Area / Team</span>
            <select
              aria-label="Area / Team"
              disabled={!allowed}
              className="w-full rounded-chip border border-slate-300 px-2 py-1.5 disabled:opacity-50"
              value={team}
              onChange={(event) => setTeam(event.target.value)}
            >
              <option value="">Choose a team…</option>
              {teams.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="mb-1 block text-slate-500">Reason (optional)</span>
            <select
              aria-label="Reason"
              disabled={!allowed}
              className="w-full rounded-chip border border-slate-300 px-2 py-1.5 disabled:opacity-50"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            >
              <option value="">No reason</option>
              {(reference.data?.status_reasons ?? []).map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="block">
          <span className="mb-1 block text-slate-500">Comment (required)</span>
          <textarea
            aria-label="Comment"
            rows={2}
            disabled={!allowed}
            className="w-full rounded-chip border border-slate-300 px-2 py-1.5 disabled:opacity-50"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />
        </label>
        {add.isError && (
          <p role="alert" className="text-red-700">
            Could not add the update: {(add.error as Error).message}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" className="rounded-chip border border-slate-300 px-3 py-1.5 hover:bg-slate-50" onClick={onClose}>
            Close
          </button>
          <button
            type="submit"
            title={hint}
            disabled={!allowed || !comment.trim() || add.isPending}
            className="rounded-chip bg-accent px-3 py-1.5 font-medium text-white disabled:opacity-40"
          >
            Add Status Update
          </button>
        </div>
      </form>
    </div>
  )
}
