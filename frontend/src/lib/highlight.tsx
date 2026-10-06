import type { ReactNode } from 'react'

/** Wraps every case-insensitive match of `query` in `<mark>` (F18-FR-05). One helper for every cell renderer. */
export function highlight(text: string, query: string): ReactNode {
  const needle = query.trim().toLowerCase()
  if (!needle || !text) return text
  const lower = text.toLowerCase()
  const parts: ReactNode[] = []
  let from = 0
  for (let at = lower.indexOf(needle); at !== -1; at = lower.indexOf(needle, from)) {
    if (at > from) parts.push(text.slice(from, at))
    parts.push(
      <mark key={at} className="rounded-sm bg-yellow-200 px-0 text-inherit">
        {text.slice(at, at + needle.length)}
      </mark>,
    )
    from = at + needle.length
  }
  if (from === 0) return text
  if (from < text.length) parts.push(text.slice(from))
  return <>{parts}</>
}
