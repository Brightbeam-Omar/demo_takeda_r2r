import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiSend } from '../../api/client'
import { useMe, type RowDetail } from '../../api/queries'
import { formatShortDate } from '../../lib/format'
import { READ_ONLY_HINT, canComment } from '../../lib/roles'
import { useToast } from '../common/Toasts'

/** F11-FR-03: the comment list and entry. Everyone but the viewer role may comment. */
export function Comments({ detail }: { detail: RowDetail }) {
  const me = useMe()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [body, setBody] = useState('')
  const allowed = canComment(me.data?.role)
  const add = useMutation({
    mutationFn: (text: string) => apiSend('POST', `/rows/${encodeURIComponent(detail.row_key)}/comments`, { body: text }),
    onSuccess: async () => {
      await queryClient.invalidateQueries()
      setBody('')
      notify('Comment added')
    },
  })
  return (
    <div className="space-y-3 text-[13px]">
      <ul className="space-y-2" data-testid="comment-list">
        {detail.comments.length === 0 ? <li className="text-slate-500">No comments yet.</li> : null}
        {detail.comments.map((comment) => (
          <li key={comment.id} className="rounded-chip border border-slate-200 px-3 py-2">
            <div className="text-xs text-slate-500">
              {comment.author_user_key} · {formatShortDate(comment.created_at)}
            </div>
            <div className="whitespace-pre-wrap">{comment.body}</div>
          </li>
        ))}
      </ul>
      <div title={allowed ? undefined : READ_ONLY_HINT} className="space-y-2">
        <textarea
          aria-label="Add a comment"
          rows={2}
          disabled={!allowed}
          placeholder="Add a comment…"
          className="w-full rounded-chip border border-slate-300 px-2 py-1.5 disabled:opacity-50"
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
        <button
          type="button"
          disabled={!allowed || !body.trim() || add.isPending}
          className="rounded-chip bg-indigo-600 px-3 py-1.5 text-white enabled:hover:bg-indigo-700 disabled:opacity-40"
          onClick={() => add.mutate(body.trim())}
        >
          Comment
        </button>
        {add.isError ? (
          <p role="alert" className="text-red-700">
            Could not add the comment: {(add.error as Error).message}
          </p>
        ) : null}
      </div>
    </div>
  )
}
