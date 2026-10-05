import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiSend, type Schemas } from '../../api/client'
import { useReference, useRowDetail } from '../../api/queries'
import { formatDate } from '../../lib/format'
import { markSaved } from '../../state/just-saved'
import { useToast } from '../common/Toasts'

type Preview = Schemas['PreviewOut']
type Body = { adjusted_date: string | null; reason_code: string | null; expedite: boolean; note: string | null }

const RAG_TEXT: Record<string, string> = { red: 'text-red-700', amber: 'text-amber-700', green: 'text-emerald-700' }

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

/** F11-FR-02: the need-by editor with a live preview before anything is saved. */
export function NeedByModal({ rowKey, onClose }: Props) {
  const detail = useRowDetail(rowKey)
  const reference = useReference()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const data = detail.data

  // The form starts from the saved values once the row has loaded (adjusting state during render, not in an effect).
  const [seededFor, setSeededFor] = useState<string | null>(null)
  const [date, setDate] = useState('')
  const [reason, setReason] = useState('')
  const [expedite, setExpedite] = useState(false)
  const [note, setNote] = useState('')
  if (data && seededFor !== data.row_key) {
    setSeededFor(data.row_key)
    setDate(data.adjusted_need_by_date ?? '')
    setReason(data.adjusted_reason_code ?? '')
    setExpedite(data.expedite)
  }

  const body: Body = {
    adjusted_date: date || null,
    reason_code: date ? reason || null : null,
    expedite,
    note: note || null,
  }
  const debouncedBody = useDebounced(body, 200)
  const path = `/rows/${encodeURIComponent(rowKey)}/need-by/preview`
  const preview = useQuery({
    queryKey: ['need-by-preview', rowKey, debouncedBody],
    queryFn: () => apiSend<Preview>('POST', path, debouncedBody),
    enabled: data !== undefined,
    retry: false,
    placeholderData: (previous) => previous,
  })

  const save = useMutation({
    mutationFn: (payload: Body) =>
      apiSend('PUT', `/rows/${encodeURIComponent(rowKey)}/need-by`, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries()
      markSaved(rowKey)
      notify('Need-by updated')
      onClose()
    },
  })

  const needsReason = Boolean(date) && !reason
  const labels = new Map(
    (reference.data?.stages ?? []).map((stage) => [String(stage.stage_key), String(stage.label)] as const),
  )
  const result = preview.data

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-slate-900/40" />
        <Dialog.Content
          aria-describedby={undefined}
          data-testid="need-by-modal"
          className="fixed top-1/2 left-1/2 z-[70] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-2xl"
        >
          <Dialog.Title className="text-lg font-semibold text-slate-900">Adjust need-by</Dialog.Title>
          <p className="text-[13px] text-slate-600">
            {data ? `${data.material_no} · batch ${data.batch_no} · lot ${data.inspection_lot_no}` : 'Loading…'}
          </p>

          <div className="mt-4 grid grid-cols-2 gap-4 text-[13px]">
            <div>
              <div className="mb-1 text-slate-500">System need-by (locked)</div>
              <div className="rounded-chip border border-slate-200 bg-slate-50 px-3 py-1.5" data-testid="system-date-box">
                {formatDate(data?.system_need_by_locked)}
              </div>
            </div>
            <label>
              <span className="mb-1 block text-slate-500">Adjusted need-by</span>
              <input
                type="date"
                aria-label="Adjusted need-by"
                className="w-full rounded-chip border border-slate-300 px-3 py-1.5"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
            </label>
            <label className="col-span-2">
              <span className="mb-1 block text-slate-500">Reason (required with a date)</span>
              <select
                aria-label="Reason"
                className="w-full rounded-chip border border-slate-300 px-3 py-1.5"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              >
                <option value="">Choose a reason…</option>
                {(reference.data?.reason_codes ?? []).map((code) => (
                  <option key={String(code.code)} value={String(code.code)}>
                    {String(code.label)}
                  </option>
                ))}
              </select>
            </label>
            <label className="col-span-2 flex items-center gap-2">
              <input type="checkbox" checked={expedite} onChange={(event) => setExpedite(event.target.checked)} />
              <span>EXPEDITE</span>
            </label>
            <label className="col-span-2">
              <span className="mb-1 block text-slate-500">Note</span>
              <textarea
                aria-label="Note"
                rows={2}
                className="w-full rounded-chip border border-slate-300 px-3 py-1.5"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
          </div>

          <div className="mt-4 rounded-card border border-indigo-100 bg-indigo-50/50 p-3 text-[13px]" data-testid="need-by-preview">
            <div className="mb-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">Preview (not saved)</div>
            {result ? (
              <dl className="grid grid-cols-[9rem_1fr] gap-y-1">
                <dt className="text-slate-500">Expected completion</dt>
                <dd data-testid="preview-expected">
                  {formatDate(result.preview.expected_completion)}
                  {result.preview.rag ? (
                    <span className={`ml-2 font-medium ${RAG_TEXT[result.preview.rag]}`} data-testid="preview-rag">
                      {result.preview.rag.toUpperCase()}
                    </span>
                  ) : null}
                  <span className="ml-2 text-slate-500">
                    now {formatDate(result.current.expected_completion)}
                    {result.current.rag ? ` (${result.current.rag})` : ''}
                  </span>
                </dd>
                <dt className="text-slate-500">Compression</dt>
                <dd data-testid="preview-compression">
                  {result.preview.compressed
                    ? `${Math.round(Number(result.preview.compression_ratio) * 100)}%: ${Object.entries(
                        result.preview.effective_slas as Record<string, number>,
                      )
                        .map(([stage, days]) => `${labels.get(stage) ?? stage} ${days} d`)
                        .join(' / ')}`
                    : 'None'}
                  <span className="ml-1 text-slate-500">
                    {result.preview.compressed ? `(${Object.values(result.preview.effective_slas as Record<string, number>).join('/')})` : ''}
                  </span>
                </dd>
              </dl>
            ) : preview.isError ? (
              <p className="text-red-700">Preview unavailable: {(preview.error as Error).message}</p>
            ) : (
              <p className="text-slate-500">Calculating…</p>
            )}
          </div>

          {save.isError ? (
            <p role="alert" className="mt-3 text-[13px] text-red-700">
              Could not save: {(save.error as Error).message}
            </p>
          ) : null}

          <div className="mt-5 flex items-center justify-between">
            <button
              type="button"
              disabled={!data?.adjusted_need_by_date || save.isPending}
              className="rounded-chip px-3 py-1.5 text-[13px] text-slate-600 enabled:hover:bg-slate-100 disabled:opacity-40"
              onClick={() => save.mutate({ adjusted_date: null, reason_code: null, expedite, note: note || null })}
            >
              Clear override
            </button>
            <div className="flex gap-2">
              <Dialog.Close className="rounded-chip border border-slate-300 px-4 py-1.5 text-[13px] hover:bg-slate-50">
                Cancel
              </Dialog.Close>
              <button
                type="button"
                disabled={needsReason || save.isPending || !data}
                className="rounded-chip bg-indigo-600 px-4 py-1.5 text-[13px] font-medium text-white enabled:hover:bg-indigo-700 disabled:opacity-40"
                onClick={() => save.mutate(body)}
              >
                {save.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
