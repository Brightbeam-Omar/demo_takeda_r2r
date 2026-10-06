import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiSend } from '../../api/client'
import { useMe, useReference, type RowDetail } from '../../api/queries'
import { READ_ONLY_HINT, canSetStatus } from '../../lib/roles'
import { markSaved } from '../../state/just-saved'
import { useToast } from '../common/Toasts'

const COLOUR_TEXT: Record<string, string> = { red: 'text-red-700', amber: 'text-amber-700', green: 'text-emerald-700' }

/**
 * F11-FR-03: the human RAG status with a reason and an owning team. It is display-only: it never changes the
 * system plan, RAG or ordering (OQ-057). Only QC leads, QA release and admins may set it.
 */
export function StatusForm({ detail }: { detail: RowDetail }) {
  const me = useMe()
  const reference = useReference()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const allowed = canSetStatus(me.data?.role)
  const current = detail.latest_status
  const [rag, setRag] = useState('')
  const [reason, setReason] = useState('')
  const [team, setTeam] = useState('')

  const teams = [...new Set((reference.data?.stages ?? []).map((stage) => String(stage.team)).filter(Boolean))]
  const save = useMutation({
    mutationFn: (payload: { rag: string | null; reason: string | null; team: string | null }) =>
      apiSend('PUT', `/rows/${encodeURIComponent(detail.row_key)}/status`, payload),
    onSuccess: async (_data, payload) => {
      await queryClient.invalidateQueries()
      markSaved(detail.row_key)
      notify(payload.rag ? 'Status updated' : 'Status cleared')
      setRag('')
      setReason('')
    },
  })

  const hint = allowed ? undefined : READ_ONLY_HINT
  return (
    <div className="space-y-2 text-[13px]" data-testid="status-form">
      <p data-testid="current-status">
        Current status:{' '}
        {current ? (
          <span className={`font-medium italic ${COLOUR_TEXT[current.colour] ?? ''}`}>
            ✎ {current.label.toUpperCase()}
            {current.team ? ` · ${current.team}` : ''}
          </span>
        ) : (
          <span className="text-slate-500">none (the system RAG applies)</span>
        )}
      </p>
      <div className="grid grid-cols-2 gap-2" title={hint}>
        <select
          aria-label="Status RAG"
          disabled={!allowed}
          className="rounded-chip border border-slate-300 px-2 py-1.5 disabled:opacity-50"
          value={rag}
          onChange={(event) => setRag(event.target.value)}
        >
          <option value="">RAG…</option>
          <option value="red">Red</option>
          <option value="amber">Amber</option>
          <option value="green">Green</option>
        </select>
        <select
          aria-label="Status team"
          disabled={!allowed}
          className="rounded-chip border border-slate-300 px-2 py-1.5 disabled:opacity-50"
          value={team}
          onChange={(event) => setTeam(event.target.value)}
        >
          <option value="">Owning team…</option>
          {teams.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <textarea
          aria-label="Status reason"
          rows={2}
          disabled={!allowed}
          placeholder="Reason (required)"
          className="col-span-2 rounded-chip border border-slate-300 px-2 py-1.5 disabled:opacity-50"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
      {save.isError ? (
        <p role="alert" className="text-red-700">
          Could not save: {(save.error as Error).message}
        </p>
      ) : null}
      <div className="flex gap-2">
        <button
          type="button"
          title={hint}
          disabled={!allowed || !rag || !reason.trim() || save.isPending}
          className="rounded-chip bg-indigo-600 px-3 py-1.5 text-white enabled:hover:bg-indigo-700 disabled:opacity-40"
          onClick={() => save.mutate({ rag, reason: reason.trim(), team: team || null })}
        >
          Set status
        </button>
        <button
          type="button"
          title={hint}
          disabled={!allowed || !current || save.isPending}
          className="rounded-chip border border-slate-300 px-3 py-1.5 enabled:hover:bg-slate-50 disabled:opacity-40"
          onClick={() => save.mutate({ rag: null, reason: null, team: null })}
        >
          Clear status
        </button>
      </div>
    </div>
  )
}
