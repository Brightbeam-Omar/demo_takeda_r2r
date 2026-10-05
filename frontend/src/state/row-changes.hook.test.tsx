import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Overview } from '../api/queries'
import { ToastProvider } from '../components/common/Toasts'
import { HIGHLIGHT_MS, useRowChanges } from './row-changes'

const wrapper = ({ children }: { children: ReactNode }) => <ToastProvider>{children}</ToastProvider>

function overview(runId: string, stage: string): Overview {
  return {
    freshness: { contract_run_id: runId },
    rows: [{ row_key: 'a', stage_key: stage, plan: { expected_completion: '2026-10-15' } }],
  } as unknown as Overview
}

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('F10-FR-11: no highlight on first load; a new contract run highlights changed rows for 5 s; a filter change does not', () => {
  const { result, rerender } = renderHook(({ data, query }) => useRowChanges(data, query), {
    wrapper,
    initialProps: { data: overview('r1', 'qc_testing'), query: 'q' },
  })
  expect(result.current.size).toBe(0)

  // The same run polled again (a clock advance changes plan fields but not the run id): nothing happens.
  rerender({ data: overview('r1', 'qc_testing'), query: 'q' })
  expect(result.current.size).toBe(0)

  rerender({ data: overview('r2', 'qa_release'), query: 'q' })
  expect([...result.current]).toEqual(['a'])

  act(() => void vi.advanceTimersByTime(HIGHLIGHT_MS + 10))
  expect(result.current.size).toBe(0)

  // A different query (filters changed) with a different run id is a first load for that query.
  rerender({ data: overview('r3', 'released'), query: 'other' })
  expect(result.current.size).toBe(0)
})
