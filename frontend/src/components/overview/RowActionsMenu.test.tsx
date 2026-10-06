import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type { Row } from '../../api/queries'
import { renderWithProviders } from '../../test-utils'
import { RowActionsMenu, menuItems } from './RowActionsMenu'

const flags = { manual_hold: false, release_on_coa: false, released: false }
const row = (over: Partial<Record<keyof typeof flags, boolean>> = {}, expected: string | null = '2026-10-20') =>
  ({
    row_key: 'RM1|B1|1',
    material_no: 'RM1',
    batch_no: 'B1',
    flags: { ...flags, ...over },
    plan: { expected_completion: expected },
  }) as unknown as Row

afterEach(() => vi.unstubAllGlobals())

const labels = (r: Row, role: string) => menuItems(r, role).map((item) => [item.label, item.disabled])

test('F18-FR-08: Alex and admin may hold and release on COA; Pat may only hold; the others see disabled items with Read-only role', () => {
  expect(labels(row(), 'qa_release')).toEqual([['+ Place Hold', null], ['Release on COA', null]])
  expect(labels(row(), 'admin')).toEqual([['+ Place Hold', null], ['Release on COA', null]])
  expect(labels(row(), 'planner')).toEqual([['+ Place Hold', null], ['Release on COA', 'Read-only role']])
  expect(labels(row(), 'viewer')).toEqual([['+ Place Hold', 'Read-only role'], ['Release on COA', 'Read-only role']])
  expect(labels(row(), 'qc_lead')).toEqual([['+ Place Hold', 'Read-only role'], ['Release on COA', 'Read-only role']])
})

test('F18-FR-08: the labels flip to Release Hold and Undo Release on COA when they are on', () => {
  expect(labels(row({ manual_hold: true, release_on_coa: true }), 'qa_release').map(([label]) => label)).toEqual(['Release Hold', 'Undo Release on COA'])
})

test('F18-FR-09/10: released rows cannot be held or COA-released, and a row with no plan cannot be COA-released', () => {
  expect(labels(row({ released: true }, null), 'qa_release')).toEqual([['+ Place Hold', 'Released rows cannot be held'], ['Release on COA', 'Needs an open cycle']])
  expect(labels(row({}, null), 'qa_release')).toEqual([['+ Place Hold', null], ['Release on COA', 'Needs an open cycle']])
})

test('F18-AC-03: Place Hold asks for a reason (at least 3 characters) and posts it, then the row refreshes', async () => {
  const calls: { url: string; body: unknown }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null })
    return new Response('{}')
  }))
  renderWithProviders(<RowActionsMenu row={row()} role="qa_release" />)
  await userEvent.click(screen.getByRole('button', { name: 'Actions for RM1 B1' }))
  await userEvent.click(screen.getByRole('menuitem', { name: '+ Place Hold' }))
  const confirm = screen.getByRole('button', { name: 'Confirm' })
  expect(confirm).toBeDisabled()
  await userEvent.type(screen.getByRole('textbox', { name: 'Reason' }), 'ab')
  expect(confirm).toBeDisabled()
  await userEvent.type(screen.getByRole('textbox', { name: 'Reason' }), 'c  ')
  expect(confirm).toBeEnabled()
  await userEvent.click(confirm)
  await waitFor(() => expect(calls[0]).toBeDefined())
  expect(calls[0]).toEqual({ url: '/api/rows/RM1%7CB1%7C1/hold', body: { on: true, reason: 'abc' } })
})

test('F18-FR-08: Release on COA posts to the COA endpoint; Undo posts on: false', async () => {
  const calls: { url: string; body: unknown }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null })
    return new Response('{}')
  }))
  renderWithProviders(<RowActionsMenu row={row({ release_on_coa: true })} role="admin" />)
  await userEvent.click(screen.getByRole('button', { name: 'Actions for RM1 B1' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Undo Release on COA' }))
  await userEvent.type(screen.getByRole('textbox', { name: 'Reason' }), 'COA was for another batch')
  await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => expect(calls[0]).toBeDefined())
  expect(calls[0]!.url).toBe('/api/rows/RM1%7CB1%7C1/coa-release')
  expect(calls[0]!.body).toEqual({ on: false, reason: 'COA was for another batch' })
})

test('F18-FR-08: a disabled item does not open the reason window', async () => {
  renderWithProviders(<RowActionsMenu row={row()} role="viewer" />)
  await userEvent.click(screen.getByRole('button', { name: 'Actions for RM1 B1' }))
  const item = screen.getByRole('menuitem', { name: '+ Place Hold' })
  expect(item).toBeDisabled()
  expect(item).toHaveAttribute('title', 'Read-only role')
  await userEvent.click(item)
  expect(screen.queryByRole('textbox', { name: 'Reason' })).not.toBeInTheDocument()
})
