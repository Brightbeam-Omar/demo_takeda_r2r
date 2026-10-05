import * as Popover from '@radix-ui/react-popover'
import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { apiGet } from '../../api/client'
import { usePersona } from '../../state/persona'
import { useToast } from '../common/Toasts'
import { describeExplanation, ExplainBody, toPlainText, type Explanation } from './ExplainContent'

interface Props {
  /** What is being explained, for the accessible name: "stage", "expected completion", "M3", … */
  what: string
  path: string
  params?: URLSearchParams
  /** Extra classes for the trigger (position, hover-only visibility). */
  className?: string
  /** Stops a click from reaching a clickable parent (a table row or a flow card). */
  children?: ReactNode
}

/** F11-FR-04. The ⓘ button and its popover; the explanation loads when it opens and can be copied. */
export function ExplainPopover({ what, path, params, className = '' }: Props) {
  const [open, setOpen] = useState(false)
  const persona = usePersona()
  const { notify } = useToast()
  const query = useQuery({
    queryKey: ['explain', path, params?.toString() ?? '', persona],
    queryFn: () => apiGet<Explanation>(path, params),
    enabled: open,
    retry: false,
    staleTime: 0,
  })
  const content = query.data ? describeExplanation(query.data) : null

  const copy = async () => {
    if (!content) return
    await navigator.clipboard.writeText(toPlainText(content))
    notify('Explanation copied')
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={`Explain ${what}`}
          data-testid={`explain-${what.replace(/\s+/g, '-').toLowerCase()}`}
          className={`rounded-full px-1 text-xs leading-none text-slate-500 hover:bg-slate-200 hover:text-indigo-700 focus-visible:opacity-100 ${className}`}
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          ⓘ
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="start"
          sideOffset={6}
          collisionPadding={12}
          data-testid="explain-popover"
          className="z-[80] w-[34rem] max-w-[90vw] rounded-card border border-slate-200 bg-white p-4 shadow-xl"
          onClick={(event) => event.stopPropagation()}
        >
          {query.isPending ? <p className="text-[13px] text-slate-500">Loading explanation…</p> : null}
          {query.isError ? (
            <p role="alert" className="text-[13px] text-red-700">
              Could not load the explanation: {(query.error as Error).message}
            </p>
          ) : null}
          {content ? (
            <>
              <ExplainBody content={content} />
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  className="rounded-chip border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50"
                  onClick={() => void copy()}
                >
                  Copy
                </button>
              </div>
            </>
          ) : null}
          <Popover.Arrow className="fill-white" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
