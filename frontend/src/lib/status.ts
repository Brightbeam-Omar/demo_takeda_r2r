import type { Row } from '../api/queries'
import { formatDate } from './format'

export type StatusKind = 'late' | 'due' | 'ok' | 'none'

/**
 * The Status column (F18-FR-03h): `LATE +Nd` when late (N days overdue), `DUE IN Nd` when amber, `ON TRACK`
 * otherwise, and `—` for rows with no plan (released or pending).
 */
export function statusOf(row: Row): { kind: StatusKind; text: string } {
  const { rag, days_remaining: remaining, expected_completion: expected } = row.plan
  if (!expected || remaining === null || !rag) return { kind: 'none', text: '—' }
  if (rag === 'red') return { kind: 'late', text: `LATE +${-remaining}d` }
  if (rag === 'amber') return { kind: 'due', text: `DUE IN ${remaining}d` }
  return { kind: 'ok', text: 'ON TRACK' }
}

/** The Expected Completion text: `17 Aug 2026`, or `17 Aug 2026 (56d over)` when overdue (F18-FR-03i). */
export function expectedText(row: Row): string {
  const { expected_completion: expected, days_remaining: remaining, late } = row.plan
  if (!expected) return '—'
  return late && remaining !== null ? `${formatDate(expected)} (${-remaining}d over)` : formatDate(expected)
}

/** The current stage's `must_complete_by` (F18-FR-03f). */
export const slaDeadline = (row: Row): string | null => row.plan.must_complete_by[row.stage_key] ?? null

export const dash = (value: string | null | undefined) => (value ? value : '—')
