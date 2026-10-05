import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { markSaved, SAVED_MS, useJustSaved } from './just-saved'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('F11-FR-02 / OQ-070: a saved row is marked for 5 s, then released, independently of other rows', () => {
  const { result } = renderHook(() => useJustSaved())
  expect(result.current.size).toBe(0)
  act(() => markSaved('a'))
  act(() => void vi.advanceTimersByTime(2000))
  act(() => markSaved('b'))
  expect([...result.current].sort()).toEqual(['a', 'b'])
  act(() => void vi.advanceTimersByTime(SAVED_MS - 2000 + 10)) // a expires, b still marked
  expect([...result.current]).toEqual(['b'])
  act(() => void vi.advanceTimersByTime(2100))
  expect(result.current.size).toBe(0)
})
