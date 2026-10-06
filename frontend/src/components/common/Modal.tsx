import * as Dialog from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  /** A line under the title (the window's explanation). */
  description?: ReactNode
  children: ReactNode
  /** `list` (default) is the wide window of the list pages; `window` is the 880 px batch window (05 v2 section 5). */
  size?: 'list' | 'window'
  testId?: string
}

const WIDTH = { list: 'w-[min(64rem,calc(100vw-2rem))]', window: 'w-[min(55rem,calc(100vw-2rem))]' }

/** A centred window over the page (F16 plan). The drawer is a non-modal side panel; this is for lists and forms. */
export function Modal({ open, onClose, title, description, children, size = 'list', testId }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/30" />
        <Dialog.Content
          aria-describedby={description ? 'modal-description' : undefined}
          data-testid={testId}
          className={`fixed top-1/2 left-1/2 z-50 flex max-h-[85vh] ${WIDTH[size]} -translate-x-1/2 -translate-y-1/2 flex-col rounded-modal bg-white shadow-2xl`}
        >
          <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="text-lg font-semibold text-slate-900">{title}</Dialog.Title>
              {description && (
                <Dialog.Description id="modal-description" className="mt-1 text-sm text-slate-600">
                  {description}
                </Dialog.Description>
              )}
            </div>
            <Dialog.Close aria-label="Close" className="rounded-chip px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800">
              ✕
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
