import { useSyncExternalStore } from 'react'

/**
 * The left sidebar's collapsed state. The user's own choice is kept apart from the automatic collapse that happens
 * while the batch drawer is open (F19 review): closing the drawer restores what the user had, and a sidebar the user
 * collapsed stays collapsed. Expanding it by hand while the drawer is open lasts until the drawer closes.
 */
interface State {
  userCollapsed: boolean
  drawerOpen: boolean
  forcedOpen: boolean
}

let state: State = { userCollapsed: false, drawerOpen: false, forcedOpen: false }
const listeners = new Set<() => void>()

function set(next: State) {
  state = next
  listeners.forEach((listener) => listener())
}

export const isCollapsed = (s: State = state) => s.userCollapsed || (s.drawerOpen && !s.forcedOpen)

export function setDrawerOpen(open: boolean): void {
  if (open === state.drawerOpen) return
  set({ ...state, drawerOpen: open, forcedOpen: false })
}

export function toggleSidebar(): void {
  if (state.drawerOpen && !state.userCollapsed) set({ ...state, forcedOpen: !state.forcedOpen })
  else set({ ...state, userCollapsed: !state.userCollapsed })
}

export function resetSidebar(): void {
  set({ userCollapsed: false, drawerOpen: false, forcedOpen: false })
}

export function useSidebarCollapsed(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => isCollapsed(),
  )
}
