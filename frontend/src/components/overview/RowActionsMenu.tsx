import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { apiSend } from '../../api/client'
import type { Row } from '../../api/queries'
import { canHold, canReleaseOnCoa, READ_ONLY_HINT } from '../../lib/roles'
import { markSaved } from '../../state/just-saved'
import { Modal } from '../common/Modal'
import { useToast } from '../common/Toasts'

type Action = 'hold' | 'coa-release'

interface Item {
  action: Action
  on: boolean
  label: string
  title: string
  done: string
  disabled: string | null
}

const MIN_REASON = 3
const MAX_REASON = 200

/** The menu items of a row, with the reason a disabled item gives (F18-FR-08, FR-09, FR-10). */
export function menuItems(row: Row, role: string | undefined): Item[] {
  const released = row.flags.released
  const planned = row.plan.expected_completion !== null // pending rows have no cycle start yet
  const held = row.flags.manual_hold
  const coa = row.flags.release_on_coa
  return [
    {
      action: 'hold',
      on: !held,
      label: held ? 'Release Hold' : '+ Place Hold',
      title: held ? 'Release the hold' : 'Place a hold',
      done: held ? 'Hold released' : 'Hold placed',
      disabled: !canHold(role) ? READ_ONLY_HINT : released ? 'Released rows cannot be held' : null,
    },
    {
      action: 'coa-release',
      on: !coa,
      label: coa ? 'Undo Release on COA' : 'Release on COA',
      title: coa ? 'Undo the release on COA' : 'Release on COA',
      done: coa ? 'Release on COA undone' : 'Release on COA set',
      disabled: !canReleaseOnCoa(role) ? READ_ONLY_HINT : released || !planned ? 'Needs an open cycle' : null,
    },
  ]
}

/** The `⋯` button of the material cell and its menu (F18-FR-08). Each action asks for a short reason first. */
export function RowActionsMenu({ row, role }: { row: Row; role: string | undefined }) {
  const [open, setOpen] = useState(false)
  const [item, setItem] = useState<Item | null>(null)
  const [reason, setReason] = useState('')
  const box = useRef<HTMLSpanElement>(null)
  const queryClient = useQueryClient()
  const { notify } = useToast()

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const send = useMutation({
    mutationFn: (chosen: Item) => apiSend('POST', `/rows/${encodeURIComponent(row.row_key)}/${chosen.action}`, { on: chosen.on, reason: reason.trim() }),
    onSuccess: async (_data, chosen) => {
      await queryClient.invalidateQueries()
      markSaved(row.row_key)
      notify(chosen.done)
      setItem(null)
      setReason('')
    },
    onError: (error) => notify(`Could not save: ${error.message}`, 'error'),
  })

  const trimmed = reason.trim()
  const valid = trimmed.length >= MIN_REASON && trimmed.length <= MAX_REASON
  return (
    <span ref={box} className="relative ml-auto self-start" onClick={(event) => event.stopPropagation()}>
      <button
        type="button"
        tabIndex={-1}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Actions for ${row.material_no} ${row.batch_no}`}
        className="rounded-chip px-1.5 text-base leading-none text-slate-500 hover:bg-slate-200 hover:text-slate-900"
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => event.key === 'Escape' && setOpen(false)}
      >
        ⋯
      </button>
      {open && (
        <div role="menu" className="absolute top-full right-0 z-30 mt-1 w-48 rounded-card border border-hairline bg-white py-1 text-left shadow-lg">
          {menuItems(row, role).map((entry) => (
            <button
              key={entry.action}
              type="button"
              role="menuitem"
              disabled={entry.disabled !== null}
              title={entry.disabled ?? entry.title}
              className="block w-full px-3 py-1.5 text-left text-sm enabled:hover:bg-panel disabled:cursor-not-allowed disabled:text-slate-400"
              onClick={() => {
                setOpen(false)
                setItem(entry)
              }}
            >
              {entry.label}
            </button>
          ))}
        </div>
      )}
      <Modal
        open={item !== null}
        onClose={() => {
          setItem(null)
          setReason('')
        }}
        title={`${item?.label.replace('+ ', '') ?? ''} — ${row.batch_no}`}
        description="A short reason is required. It is saved with the change and in the audit log."
      >
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (item && valid) send.mutate(item)
          }}
        >
          <label className="block text-sm font-medium">
            Reason
            <textarea
              autoFocus
              rows={3}
              maxLength={MAX_REASON}
              className="mt-1 w-full rounded-chip border border-slate-300 px-2 py-1.5 text-sm font-normal"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <p className="text-xs text-slate-500">
            {trimmed.length}/{MAX_REASON} characters (at least {MIN_REASON})
          </p>
          <div className="flex justify-end gap-2">
            <button type="button" className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm" onClick={() => setItem(null)}>
              Cancel
            </button>
            <button type="submit" disabled={!valid || send.isPending} className="rounded-chip bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">
              Confirm
            </button>
          </div>
        </form>
      </Modal>
    </span>
  )
}
