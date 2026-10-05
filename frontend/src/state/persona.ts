import { useSyncExternalStore } from 'react'

const KEY = 'r2r.persona'
const listeners = new Set<() => void>()

/** The chosen persona's user_key, kept in sessionStorage (F10-FR-02). Null means "server default". */
export function getPersona(): string | null {
  return sessionStorage.getItem(KEY)
}

export function setPersona(userKey: string): void {
  sessionStorage.setItem(KEY, userKey)
  listeners.forEach((listener) => listener())
}

/** Subscribe to persona changes outside React (the query client refetches everything on a switch). */
export function onPersonaChange(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function usePersona(): string | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    getPersona,
  )
}
