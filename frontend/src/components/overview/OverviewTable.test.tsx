import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import type { Row } from '../../api/queries'
import { renderWithProviders } from '../../test-utils'
import { OverviewTable } from './OverviewTable'

const flags = { on_hold: false, erp_hold: false, manual_hold: false, release_on_coa: false, released: false, erp_blocked: false, re_eval: false, offsite: false, full_spec: false, expedite: false, ud_rejected: false, lims_rejected: false, air_gap: false, late: false }

function makeRow(n: number, over: Partial<Row> = {}): Row {
  return {
    row_key: `RM${n}|B20${n}|1000${n}`,
    material_no: `RM${n}`,
    material_desc: 'Excipient 017',
    supplier_batch: `SB-${n}`,
    material_class: 'drug_substance',
    campaign: 'CMP-ALPHA',
    storage_location: '0100',
    location_type: 'onsite',
    batch_no: `B20${n}`,
    inspection_lot_no: `1000${n}`,
    stage_key: 'sampling',
    stage_label: 'Sampling',
    inbound_light: 'green',
    deviation_light: 'amber',
    system_need_by_locked: '2026-12-03',
    adjusted_need_by_date: null,
    next_inspection_date: '2027-11-03',
    qc_testing_entry: '2026-10-10',
    gr_date: '2026-10-01',
    lims_approved_date: null,
    ud_date: null,
    days_in_stage: n,
    manual_status: null,
    flags,
    plan: { expected_completion: '2026-10-20', must_complete_by: { sampling: '2026-10-18' }, rag: 'green', days_remaining: 8, late: false },
    ...over,
  } as unknown as Row
}

const late = makeRow(2, { plan: { expected_completion: '2026-08-17', must_complete_by: { sampling: '2026-08-17' }, rag: 'red', days_remaining: -56, late: true } as unknown as Row['plan'], flags: { ...flags, late: true, on_hold: true, erp_hold: true } })
const amber = makeRow(3, { plan: { expected_completion: '2026-10-14', must_complete_by: { sampling: '2026-10-14' }, rag: 'amber', days_remaining: 2, late: false } as unknown as Row['plan'], adjusted_need_by_date: '2026-11-26' })
const released = makeRow(4, { stage_key: 'released', plan: { expected_completion: null, must_complete_by: {}, rag: null, days_remaining: null, late: false } as unknown as Row['plan'], flags: { ...flags, released: true } })

const show = (rows: Row[], extra: Partial<Parameters<typeof OverviewTable>[0]> = {}) =>
  renderWithProviders(
    <OverviewTable
      rows={rows}
      stageIndex={new Map([['sampling', 3]])}
      canEdit
      changedKeys={new Set()}
      bookmarks={new Set()}
      search={{ value: '', onChange: () => undefined }}
      columnsKey="test"
      onToggleBookmark={() => undefined}
      {...extra}
    />,
  )

beforeEach(() => sessionStorage.clear())

test('F18-AC-01: the default view shows the 16 columns in order, and the four hidden ones join through Columns', async () => {
  show([makeRow(1)])
  const headers = () => screen.getAllByRole('columnheader').map((h) => h.textContent?.replace(/[▲▼]/g, '').trim())
  expect(headers()).toEqual([
    'Material', 'Campaign', 'Class', 'Batch', 'Lot #', 'Inbound', 'Deviation', 'Location', 'Stage',
    'System Needs-By', 'Adjusted Date', 'SLA Deadline', 'Next Inspection', 'Days In Stage', 'Status', 'Expected Completion',
  ])
  await userEvent.click(screen.getAllByRole('button', { name: /Columns/ })[0]!)
  const panel = screen.getByRole('group', { name: 'Columns' })
  expect(within(panel).getAllByRole('checkbox')).toHaveLength(20)
  await userEvent.click(within(panel).getByRole('checkbox', { name: 'Goods Receipt Date' }))
  expect(headers()).toContain('Goods Receipt Date')
  expect(headers()).toHaveLength(17)
  await userEvent.click(within(panel).getByRole('button', { name: 'Reset' }))
  expect(headers()).toHaveLength(16)
})

test('F18-FR-02: the hidden column is named after the profile term for the LIMS', async () => {
  show([makeRow(1)])
  await userEvent.click(screen.getAllByRole('button', { name: /Columns/ })[0]!)
  expect(within(screen.getByRole('group', { name: 'Columns' })).getByRole('checkbox', { name: 'LIMS Approved Date' })).toBeInTheDocument()
})

test('F18-FR-03: the material cell has star, code, description, supplier batch and tag chips', () => {
  show([late])
  const cell = within(screen.getByTestId('batch-row')).getAllByRole('cell')[0]!
  expect(within(cell).getByText('RM2')).toHaveClass('font-semibold')
  expect(within(cell).getByText('Excipient 017')).toBeInTheDocument()
  expect(within(cell).getByText('SB-2')).toBeInTheDocument()
  expect(within(cell).getByText('LATE')).toBeInTheDocument()
  expect(within(cell).getByText('ON HOLD')).toBeInTheDocument()
  expect(within(cell).getByRole('button', { name: 'Bookmark RM2|B202|10002' })).toBeInTheDocument()
})

test('F18-AC-07: a late row reads LATE +56d with a red Expected Completion and (56d over)', () => {
  show([late])
  expect(screen.getByTestId('status-cell')).toHaveTextContent('LATE +56d')
  expect(screen.getByTestId('status-cell')).toHaveClass('text-red-700')
  expect(screen.getByTestId('expected-cell')).toHaveTextContent('17 Aug 2026 (56d over)')
  expect(screen.getByTestId('expected-cell')).toHaveClass('text-red-700')
})

test('F18-AC-07: a row due in 2 days reads DUE IN 2d in amber; an on-track row reads ON TRACK; a released row a dash', () => {
  show([amber, makeRow(1), released])
  const status = screen.getAllByTestId('status-cell')
  expect(status.map((cell) => cell.textContent)).toEqual(['DUE IN 2d', 'ON TRACK', '—'])
  expect(status[0]).toHaveClass('text-amber-700')
  expect(status[1]).toHaveClass('text-emerald-700')
  expect(screen.getAllByTestId('expected-cell')[1]).not.toHaveAttribute('data-late')
})

test('F18-AC-07: DUE IN reads literally on the day itself (OQ-106)', () => {
  show([makeRow(5, { plan: { expected_completion: '2026-10-12', must_complete_by: {}, rag: 'amber', days_remaining: 0, late: false } as unknown as Row['plan'] })])
  expect(screen.getByTestId('status-cell')).toHaveTextContent('DUE IN 0d')
})

test('F18-FR-03: SLA deadline is the current stage must_complete_by with a RAG dot; days are 5d style; dates are 12 Oct 2026', () => {
  show([makeRow(7)])
  expect(screen.getByTestId('sla-deadline')).toHaveTextContent('18 Oct 2026')
  const row = screen.getByTestId('batch-row')
  expect(within(row).getByText('7d')).toBeInTheDocument()
  expect(within(row).getByText('3 Dec 2026')).toBeInTheDocument()
  expect(within(row).getByText('3 Nov 2027')).toBeInTheDocument() // Next Inspection
})

test('F18-FR-03: Adjusted Date shows the value with a pencil, or + set date ✎, and opens the need-by modal', async () => {
  const edit = vi.fn()
  show([amber, makeRow(1)], { onEditRow: edit })
  const buttons = screen.getAllByRole('button', { name: 'Edit need-by' })
  expect(buttons[0]).toHaveTextContent('26 Nov 2026 ✎')
  expect(buttons[1]).toHaveTextContent('+ set date ✎')
  await userEvent.click(buttons[1]!)
  expect(edit).toHaveBeenCalledWith('RM1|B201|10001')
})

test('F18-FR-03: the pencil is disabled for a read-only role', () => {
  show([makeRow(1)], { canEdit: false })
  expect(screen.getByRole('button', { name: 'Edit need-by' })).toBeDisabled()
})

test('F18-FR-03: the batch is a link that opens the batch window', async () => {
  const open = vi.fn()
  show([makeRow(1)], { onOpenRow: open })
  await userEvent.click(screen.getByRole('button', { name: 'B201' }))
  expect(open).toHaveBeenCalledWith('RM1|B201|10001')
})

test('F18-FR-03: the sample-count badge and the status-log line appear only when published (F19)', () => {
  const { unmount } = show([makeRow(1)])
  expect(screen.getByTestId('batch-row')).not.toHaveTextContent('Customer reply')
  unmount()
  show([makeRow(1, { sample_count: 3, latest_status: 'Customer reply awaited' } as unknown as Partial<Row>)])
  expect(screen.getByTestId('batch-row')).toHaveTextContent('Customer reply awaited')
})

test('F18-FR-04: late, rejected, on-hold and air-gap rows get the tint and the red bar; ERP-blocked and plain rows do not', () => {
  const rejected = makeRow(6, { flags: { ...flags, ud_rejected: true } })
  const gap = makeRow(8, { flags: { ...flags, air_gap: true } })
  const blocked = makeRow(9, { flags: { ...flags, erp_blocked: true } })
  const held = makeRow(10, { flags: { ...flags, on_hold: true, manual_hold: true } })
  show([late, rejected, gap, held, blocked, makeRow(1)])
  const rows = screen.getAllByTestId('batch-row')
  const tinted = rows.map((r) => r.style.backgroundColor === 'rgb(254, 242, 242)')
  expect(tinted).toEqual([true, true, true, true, false, false])
  expect(within(rows[0]!).getAllByRole('cell')[0]!.getAttribute('style')).toContain('inset 3px 0 0')
  expect(within(rows[4]!).getAllByRole('cell')[0]!.getAttribute('style')).toBeNull()
})

test('F18-AC-01: no cell may truncate its text: nothing in the table is clipped by an ellipsis or overflow-hidden', () => {
  show([late, amber, makeRow(1)])
  const table = screen.getByRole('grid')
  expect(table.querySelectorAll('.truncate, .text-ellipsis, .overflow-hidden').length).toBe(0)
  expect(table).toHaveClass('whitespace-nowrap')
})

test('F18-FR-06: the count reads 1–3 of 3 lots (n batches), counting a re-evaluated batch once', () => {
  const reeval = makeRow(1, { row_key: 'RM1|B201|2', inspection_lot_no: '2' })
  show([makeRow(1), reeval, makeRow(2)])
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–3 of 3 lots (2 batches)')
})

test('F18-FR-05: the search text marks the matches in the Batch cell and the count follows', async () => {
  show([makeRow(1), makeRow(2), makeRow(3)], { search: { value: 'B202', onChange: () => undefined } })
  expect(screen.getAllByTestId('batch-row')).toHaveLength(1)
  expect(document.querySelector('mark')).toHaveTextContent('B202')
  expect(within(screen.getByRole('button', { name: 'B202' })).getByText('B202').tagName).toBe('MARK')
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–1 of 1 lot (1 batch)')
})
