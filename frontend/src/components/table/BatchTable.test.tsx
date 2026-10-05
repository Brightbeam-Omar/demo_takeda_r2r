import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, expect, test } from 'vitest'
import type { Row } from '../../api/queries'
import { BatchTable } from './BatchTable'
import { renderWithProviders } from '../../test-utils'

// jsdom has no layout, so give the scroll container a size for the virtualiser.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 400 })
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 1200 })
})

function makeRow(n: number): Row {
  return {
    row_key: `RM${n}|B${n}|1`,
    material_no: `RM${n}`,
    material_desc: 'Excipient',
    material_class: 'drug_substance',
    campaign: 'CMP-ALPHA',
    storage_location: '0100',
    location_type: 'onsite',
    batch_no: `B${n}`,
    stage_key: 'sampling',
    stage_label: 'Sampling',
    inbound_light: 'green',
    deviation_light: 'green',
    system_need_by_locked: '2026-12-03',
    adjusted_need_by_date: null,
    days_in_stage: n,
    manual_status: null,
    flags: {},
    plan: { expected_completion: '2026-10-20', rag: 'green', days_remaining: 8 },
  } as unknown as Row
}

test('F10-FR-09: 1,000 rows render virtualised (only a window of rows is in the DOM)', () => {
  renderWithProviders(<BatchTable rows={Array.from({ length: 1000 }, (_, i) => makeRow(i))} stageIndex={new Map()} canEdit={false} changedKeys={new Set()} />)
  expect(screen.getByTestId('row-count')).toHaveTextContent('1000 lots · 1000 batches')
  expect(screen.getAllByTestId('batch-row').length).toBeLessThan(100)
})

test('F10-FR-09: a per-column filter narrows the rows and a header click sorts them (days, descending first row)', async () => {
  const rows = [makeRow(5), makeRow(30), makeRow(12)]
  renderWithProviders(<BatchTable rows={rows} stageIndex={new Map()} canEdit={false} changedKeys={new Set()} />)
  expect(screen.queryByRole('textbox', { name: 'Filter Batch' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Filter by Batch' }))
  await userEvent.type(screen.getByRole('textbox', { name: 'Filter Batch' }), 'B3')
  expect(screen.getByTestId('row-count')).toHaveTextContent('1 lot · 1 batch')
  await userEvent.clear(screen.getByRole('textbox', { name: 'Filter Batch' }))
  const days = screen.getByRole('button', { name: 'Days in stage' })
  await userEvent.click(days)
  expect(screen.getAllByTestId('batch-row')[0]).toHaveAttribute('data-row-key', 'RM30|B30|1')
  await userEvent.click(days)
  expect(screen.getAllByTestId('batch-row')[0]).toHaveAttribute('data-row-key', 'RM5|B5|1')
})

test('F10 review: a batch with a re-evaluation lot is two lots but one batch', () => {
  const rows = [makeRow(7), { ...makeRow(7), row_key: 'RM7|B7|2', inspection_lot_no: '2' } as Row, makeRow(8)]
  renderWithProviders(<BatchTable rows={rows} stageIndex={new Map()} canEdit={false} changedKeys={new Set()} />)
  expect(screen.getByTestId('row-count')).toHaveTextContent('3 lots · 2 batches')
})

test('F16-FR-04: the star column bookmarks a row without opening the drawer', async () => {
  const opened: string[] = []
  const toggled: [string, boolean][] = []
  renderWithProviders(
    <BatchTable
      rows={[makeRow(1), makeRow(2)]}
      stageIndex={new Map()}
      canEdit={false}
      changedKeys={new Set()}
      bookmarks={new Set(['RM2|B2|1'])}
      onToggleBookmark={(rowKey, on) => toggled.push([rowKey, on])}
      onOpenRow={(rowKey) => opened.push(rowKey)}
    />,
  )
  expect(screen.getByRole('button', { name: 'Remove bookmark from RM2|B2|1' })).toHaveAttribute('aria-pressed', 'true')
  await userEvent.click(screen.getByRole('button', { name: 'Bookmark RM1|B1|1' }))
  await userEvent.click(screen.getByRole('button', { name: 'Remove bookmark from RM2|B2|1' }))
  expect(toggled).toEqual([
    ['RM1|B1|1', true],
    ['RM2|B2|1', false],
  ])
  expect(opened).toEqual([])
})

test('F16-FR-04: without a toggle handler there is no star column', () => {
  renderWithProviders(<BatchTable rows={[makeRow(1)]} stageIndex={new Map()} canEdit={false} changedKeys={new Set()} />)
  expect(screen.queryByRole('button', { name: /Bookmark/ })).not.toBeInTheDocument()
})
