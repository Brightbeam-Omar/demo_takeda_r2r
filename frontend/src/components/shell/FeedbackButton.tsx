import * as Dialog from '@radix-ui/react-dialog'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { apiSend } from '../../api/client'
import { useToast } from '../common/Toasts'

const MAX_LENGTH = 2000

/** F15-FR-06. A floating button on every page. The page is filled in from the route. */
export function FeedbackButton() {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const { pathname } = useLocation()
  const { notify } = useToast()
  const send = useMutation({
    mutationFn: () =>
      apiSend('POST', '/feedback', {
        page: pathname.slice(0, 200),
        message: message.trim(),
      }),
    onSuccess: () => {
      notify('Thanks, your feedback was sent', 'info')
      setMessage('')
      setOpen(false)
    },
    onError: (error: Error) => notify(`Could not send feedback: ${error.message}`, 'error'),
  })
  const valid = message.trim().length > 0 && message.length <= MAX_LENGTH

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          data-testid="feedback-button"
          className="fixed bottom-4 right-4 z-30 rounded-pill bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg hover:opacity-90"
        >
          <span aria-hidden>💬</span> Feedback
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30" />
        <Dialog.Content
          data-testid="feedback-modal"
          className="fixed top-1/2 left-1/2 z-50 w-[28rem] -translate-x-1/2 -translate-y-1/2 rounded-modal bg-white p-5 shadow-xl"
        >
          <Dialog.Title className="text-lg font-semibold">Send feedback</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-ink-2">
            Page: <span data-testid="feedback-page">{pathname}</span>
          </Dialog.Description>
          <textarea
            aria-label="Feedback message"
            className="mt-3 h-32 w-full rounded-chip border border-hairline p-2 text-sm"
            placeholder="What worked, what did not, what is missing?"
            maxLength={MAX_LENGTH}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
          <div className="mt-3 flex justify-end gap-2">
            <Dialog.Close className="rounded-pill border border-hairline px-4 py-1.5 text-sm hover:bg-panel">
              Cancel
            </Dialog.Close>
            <button
              type="button"
              disabled={!valid || send.isPending}
              className="rounded-pill bg-accent px-4 py-1.5 text-sm text-white disabled:opacity-40"
              onClick={() => send.mutate()}
            >
              Send
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
