import { Modal } from './Modal'

interface Props {
  title: string
  message: string
  confirmLabel: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** A small yes/no window for actions that start real work (F21-FR-05). */
export function ConfirmDialog({ title, message, confirmLabel, busy = false, onConfirm, onCancel }: Props) {
  return (
    <Modal open onClose={onCancel} title={title} size="window" testId="confirm-dialog">
      <p className="text-sm text-ink">{message}</p>
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          disabled={busy}
          className="rounded-chip bg-accent px-3 py-1.5 text-sm font-medium text-white enabled:hover:opacity-90 disabled:opacity-50"
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}
