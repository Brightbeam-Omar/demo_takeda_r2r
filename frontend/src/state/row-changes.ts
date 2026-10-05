import { useEffect, useState } from 'react'
import type { Overview, Row } from '../api/queries'
import { useToast } from '../components/common/Toasts'

export const HIGHLIGHT_MS = 5000

type Signature = Map<string, string>

/** What makes a row "moved": a new row, a different stage or a different expected completion (F10 plan). */
export function signatures(rows: Row[]): Signature {
  return new Map(rows.map((row) => [row.row_key, `${row.stage_key}|${row.plan.expected_completion ?? ''}`]))
}

export function changedRowKeys(previous: Signature, next: Signature): Set<string> {
  const changed = new Set<string>()
  for (const [key, signature] of next) if (previous.get(key) !== signature) changed.add(key)
  return changed
}

interface Seen {
  runId: string | null
  query: string
  signature: Signature
}

/**
 * F10-FR-11. When `contract_run_id` changes between polls of the same query, toast "Updated just now" and
 * return the changed row keys for 5 s. First loads, filter changes and demo-clock ticks never highlight (OQ-065).
 */
export function useRowChanges(data: Overview | undefined, query: string): ReadonlySet<string> {
  const { notify } = useToast()
  const [seen, setSeen] = useState<Seen | null>(null)
  const [changed, setChanged] = useState<ReadonlySet<string>>(new Set())
  const [token, setToken] = useState(0)

  const runId = data?.freshness.contract_run_id ?? null
  if (data && (seen === null || seen.query !== query || seen.runId !== runId)) {
    const signature = signatures(data.rows)
    const sameQuery = seen !== null && seen.query === query
    setSeen({ runId, query, signature })
    if (sameQuery && seen) {
      setChanged(changedRowKeys(seen.signature, signature))
      setToken(token + 1)
    }
  }

  useEffect(() => {
    if (token === 0) return
    notify('Updated just now')
    const timer = setTimeout(() => setChanged(new Set()), HIGHLIGHT_MS)
    return () => clearTimeout(timer)
  }, [token, notify])

  return changed
}
