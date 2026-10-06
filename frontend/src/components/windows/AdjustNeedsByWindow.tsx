import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiSend, type Schemas } from '../../api/client'
import { useMe, useReference, type RowDetail } from '../../api/queries'
import { formatDate } from '../../lib/format'
import { READ_ONLY_HINT, canEditNeedBy } from '../../lib/roles'
import { OTHER_REASON, needByDelta } from '../../lib/windows'
import { markSaved } from '../../state/just-saved'
import { useToast } from '../common/Toasts'
import { BatchWindowShell, SummaryPanel, materialLine } from './BatchWindowShell'

type Preview = Schemas['PreviewOut']
type Body = { adjusted_date: string | null; reason_code: string | null; expedite: boolean; note: string | null }

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(timer)
  }, [value, ms])
  return debounced
}

interface Props {
  rowKey: string
  onClose: () => void
}

/** W6 Adjust Needs-by Date (F19, replaces F11's need-by modal): set the date and reason, see the compressed deadlines. */
export function AdjustNeedsByWindow({ rowKey, onClose }: Props) {
  return (
    <BatchWindowShell
      rowKey={rowKey}
      onClose={onClose}
      testId="needby-window"
      title={(detail) => `Adjust Needs-by Date — ${detail.batch_no}`}
    >
      {(detail) => <NeedByBody detail={detail} onClose={onClose} />}
    </BatchWindowShell>
  )
}

function NeedByBody({ detail, onClose }: { detail: RowDetail; onClose: () => void }) {
  const me = useMe()
  const reference = useReference()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const allowed = canEditNeedBy(me.data?.role)
  const hint = allowed ? undefined : READ_ONLY_HINT
  const [date, setDate] = useState(detail.adjusted_need_by_date ?? '')
  const [reason, setReason] = useState(detail.adjusted_reason_code ?? '')
  const [expedite, setExpedite] = useState(detail.expedite)
  const [note, setNote] = useState('')

  const body: Body = { adjusted_date: date || null, reason_code: date ? reason || null : null, expedite, note: note.trim() || null }
  const debounced = useDebounced(body, 200)
  const preview = useQuery({
    queryKey: ['need-by-preview', detail.row_key, debounced],
    queryFn: () => apiSend<Preview>('POST', `/rows/${encodeURIComponent(detail.row_key)}/need-by/preview`, debounced),
    retry: false,
    placeholderData: (previous) => previous,
  })
  const save = useMutation({
    mutationFn: (payload: Body) => apiSend('PUT', `/rows/${encodeURIComponent(detail.row_key)}/need-by`, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries()
      markSaved(detail.row_key)
      notify('Need-by updated')
      onClose()
    },
  })

  const delta = needByDelta(detail.system_need_by_locked, date || null)
  const labels = new Map((reference.data?.stages ?? []).map((stage) => [String(stage.stage_key), String(stage.label)] as const))
  const result = preview.data
  const deadlines = date && result ? Object.entries(result.preview.must_complete_by as Record<string, string>) : []
  const needsReason = Boolean(date) && !reason
  const needsNote = reason === OTHER_REASON && !note.trim()
  const reasons = reference.data?.reason_codes ?? []

  return (
    <div className="space-y-3 text-[13px]">
      <SummaryPanel
        items={[
          ['Material', materialLine(detail)],
          [
            'System Needs-by',
            <span key="system" data-testid="system-date-box">
              {formatDate(detail.system_need_by_locked)}
            </span>,
          ],
        ]}
      />
      <label className="block">
        <span className="mb-1 block font-medium">New Adjusted Date</span>
        <input
          type="date"
          aria-label="New Adjusted Date"
          disabled={!allowed}
          className="rounded-chip border border-slate-300 px-3 py-1.5 disabled:opacity-50"
          value={date}
          onChange={(event) => setDate(event.target.value)}
        />
      </label>
      {delta && (
        <p className={`font-medium ${delta.tone === 'red' ? 'text-red-700' : 'text-emerald-700'}`} data-testid="needby-delta" data-tone={delta.tone}>
          {delta.text}
        </p>
      )}
      <label className="block">
        <span className="mb-1 block font-medium">Reason for Change *</span>
        <select
          aria-label="Reason for Change"
          disabled={!allowed}
          className="w-full rounded-chip border border-slate-300 px-3 py-1.5 disabled:opacity-50"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        >
          <option value="">— Select a reason —</option>
          {reasons.map((code) => (
            <option key={String(code.code)} value={String(code.code)}>
              {String(code.label)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2">
        <input type="checkbox" disabled={!allowed} checked={expedite} onChange={(event) => setExpedite(event.target.checked)} />
        <span>Expedite — tag this batch as expedited (tracked as a separate metric)</span>
      </label>
      {date && (
        <div className="rounded-card border border-indigo-100 bg-indigo-50/50 p-3" data-testid="needby-preview">
          <div className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            {result?.preview.compressed ? 'Compressed stage deadlines (preview)' : 'Stage deadlines (preview)'}
          </div>
          {result?.preview.compressed && <p className="text-slate-600">Every remaining stage&apos;s SLA budget is compressed proportionally.</p>}
          {result ? (
            <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-1" data-testid="preview-deadlines">
              {deadlines.map(([stage, when]) => (
                <li key={stage}>
                  • {labels.get(stage) ?? stage}: {formatDate(when)}
                </li>
              ))}
            </ul>
          ) : preview.isError ? (
            <p className="text-red-700">Preview unavailable: {(preview.error as Error).message}</p>
          ) : (
            <p className="text-slate-500">Calculating…</p>
          )}
          <p className="mt-1 text-xs text-slate-500">Estimates for sense-checking; the scheduled pipeline run remains authoritative.</p>
        </div>
      )}
      <label className="block">
        <span className="mb-1 block font-medium">Notes {reason === OTHER_REASON ? '(required)' : '(optional)'}</span>
        <textarea
          aria-label="Notes"
          rows={2}
          disabled={!allowed}
          className="w-full rounded-chip border border-slate-300 px-3 py-1.5 disabled:opacity-50"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      {save.isError && (
        <p role="alert" className="text-red-700">
          Could not save: {(save.error as Error).message}
        </p>
      )}
      <div className="flex items-center justify-between pt-1">
        <div>
          {detail.adjusted_need_by_date && (
            <button
              type="button"
              title={hint}
              disabled={!allowed || save.isPending}
              className="rounded-chip px-3 py-1.5 text-slate-600 enabled:hover:bg-slate-100 disabled:opacity-40"
              onClick={() => save.mutate({ adjusted_date: null, reason_code: null, expedite, note: note.trim() || null })}
            >
              Clear override
            </button>
          )}
        </div>
        <div className="flex gap-2">
          <button type="button" className="rounded-chip border border-slate-300 px-4 py-1.5 hover:bg-slate-50" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            title={hint}
            disabled={!allowed || !date || needsReason || needsNote || save.isPending}
            className="rounded-chip bg-accent px-4 py-1.5 font-medium text-white disabled:opacity-40"
            onClick={() => save.mutate(body)}
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
