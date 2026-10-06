import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * The batch drawer and the five batch windows live in the URL (F19-FR-01, OQ-114, OQ-116):
 *
 * - `?row=<row_key>` opens the drawer.
 * - `?win=<inbound|quality|status|samples|needby>&row=<row_key>` opens one window. Alone, closing it removes both.
 * - `?win=…&row=…&drawer=open` is a window on top of the drawer: closing it leaves `?row=…`, so the drawer stays.
 */
export const WINDOW_NAMES = ['inbound', 'quality', 'status', 'samples', 'needby'] as const
export type WindowName = (typeof WINDOW_NAMES)[number]

export interface BatchView {
  /** The row whose drawer is showing (also while a window sits on top of it). */
  drawerRow: string | null
  win: WindowName | null
  /** The row the window is about. */
  winRow: string | null
}

const isWindow = (value: string | null): value is WindowName => WINDOW_NAMES.includes(value as WindowName)

export function readBatchView(search: URLSearchParams): BatchView {
  const row = search.get('row')
  const requested = search.get('win')
  const win = row && isWindow(requested) ? requested : null
  const drawerRow = row && (!win || search.get('drawer') === 'open') ? row : null
  return { drawerRow, win, winRow: win ? row : null }
}

function copy(search: URLSearchParams): URLSearchParams {
  return new URLSearchParams(search)
}

export function withDrawer(search: URLSearchParams, rowKey: string | null): URLSearchParams {
  const next = copy(search)
  next.delete('win')
  next.delete('drawer')
  if (rowKey) next.set('row', rowKey)
  else next.delete('row')
  return next
}

export function withWindow(search: URLSearchParams, win: WindowName, rowKey: string): URLSearchParams {
  const over = readBatchView(search).drawerRow !== null
  const next = copy(search)
  next.set('win', win)
  next.set('row', rowKey)
  if (over) next.set('drawer', 'open')
  else next.delete('drawer')
  return next
}

export function withoutWindow(search: URLSearchParams): URLSearchParams {
  const next = copy(search)
  const keepDrawer = next.get('drawer') === 'open'
  next.delete('win')
  next.delete('drawer')
  if (!keepDrawer) next.delete('row')
  return next
}

/** The drawer and window state of the Overview, with history replace so Back is not filled with open/close steps. */
export function useBatchView() {
  const [search, setSearch] = useSearchParams()
  const view = useMemo(() => readBatchView(search), [search])
  const update = useCallback(
    (change: (current: URLSearchParams) => URLSearchParams) => setSearch((current) => change(current), { replace: true }),
    [setSearch],
  )
  const openDrawer = useCallback((rowKey: string | null) => update((current) => withDrawer(current, rowKey)), [update])
  const openWindow = useCallback((win: WindowName, rowKey: string) => update((current) => withWindow(current, win, rowKey)), [update])
  const closeWindow = useCallback(() => update(withoutWindow), [update])
  return { ...view, openDrawer, openWindow, closeWindow }
}
