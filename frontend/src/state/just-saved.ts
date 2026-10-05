import { useSyncExternalStore } from 'react'

/**
 * Rows the user has just saved, highlighted for 5 s (F11-FR-02, OQ-070). It is separate from the contract-run
 * highlight in `row-changes.ts`: a save changes the plan but never the contract run.
 */
export const SAVED_MS = 5000

let saved: ReadonlySet<string> = new Set()
const listeners = new Set<() => void>()

function emit(next: ReadonlySet<string>) {
  saved = next
  listeners.forEach((listener) => listener())
}

export function markSaved(rowKey: string): void {
  emit(new Set(saved).add(rowKey))
  setTimeout(() => {
    const next = new Set(saved)
    next.delete(rowKey)
    emit(next)
  }, SAVED_MS)
}

export function useJustSaved(): ReadonlySet<string> {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => saved,
  )
}
