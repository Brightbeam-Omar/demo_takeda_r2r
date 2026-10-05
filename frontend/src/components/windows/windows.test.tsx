import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { AdjustedNeedByWindow } from './AdjustedNeedByWindow'
import { ExpectedDeliveriesWindow } from './ExpectedDeliveriesWindow'
import { InsightsWindow, gapTone } from './InsightsWindow'

afterEach(() => vi.unstubAllGlobals())

function stub(routes: Record<string, unknown>, seen: string[] = []) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      seen.push(url)
      const hit = Object.entries(routes).find(([prefix]) => url.startsWith(prefix))
      return hit ? new Response(JSON.stringify(hit[1])) : new Response('nf', { status: 404 })
    }),
  )
}

const adjustedBody = {
  total: 2,
  rows: [
    { row_key: 'k1', batch_no: 'B2077', material_no: 'RM10031', material_desc: 'Lactose', system_need_by_date: '2026-12-03', adjusted_date: '2026-11-26', delta_days: -7, reason_code: 'CAMPAIGN_PULLED_FORWARD', reason_label: 'Campaign pulled forward', set_by: 'Pat', set_at: '2026-10-12T07:00:00Z' },
    { row_key: 'k2', batch_no: 'B2100', material_no: 'RM10032', material_desc: 'Sucrose', system_need_by_date: '2026-12-01', adjusted_date: '2026-12-04', delta_days: 3, reason_code: 'CAMPAIGN_PUSHED_OUT', reason_label: 'Campaign pushed out', set_by: 'Admin', set_at: '2026-10-12T06:00:00Z' },
  ],
}

const wrap = (ui: React.ReactElement) => renderWithProviders(<MemoryRouter>{ui}</MemoryRouter>)

test('F16-FR-07 / AC-04: the adjusted window has the spec columns, Δ coloured by direction, the reason label and Set By', async () => {
  stub({ '/api/overview/adjusted': adjustedBody })
  wrap(<AdjustedNeedByWindow open onClose={vi.fn()} params={new URLSearchParams()} />)
  expect(await screen.findByRole('heading', { name: 'Adjusted Needs-by Dates — Planner Overrides' })).toBeInTheDocument()
  await screen.findAllByTestId('window-row')
  expect(screen.getAllByRole('columnheader').map((h) => h.textContent?.replace(/[▲▼]/g, ''))).toEqual([
    'Batch', 'Material', 'ERP Date', 'Adjusted Date', 'Δ Days', 'Reason', 'Set By',
  ])
  const [first, second] = screen.getAllByTestId('window-row')
  expect(within(first!).getByText('RM10031')).toBeInTheDocument()
  expect(within(first!).getByText('Lactose')).toBeInTheDocument() // the description sits under the code
  expect(within(first!).getByText('3 Dec 2026')).toBeInTheDocument()
  expect(within(first!).getByText('26 Nov 2026')).toBeInTheDocument()
  const pulled = within(first!).getByText('−7')
  expect(pulled.className).toContain('text-red-700')
  expect(within(first!).getByText('Campaign pulled forward')).toBeInTheDocument()
  expect(within(first!).getByText('Pat')).toBeInTheDocument()
  const pushed = within(second!).getByText('+3')
  expect(pushed.className).toContain('text-emerald-700')
})

test('F16-FR-07: the window keeps the server order (newest override first) and sends the banner filters', async () => {
  const seen: string[] = []
  stub({ '/api/overview/adjusted': adjustedBody }, seen)
  wrap(<AdjustedNeedByWindow open onClose={vi.fn()} params={new URLSearchParams('campaign[]=CMP-ALPHA&bookmarked=true')} />)
  await screen.findByText('B2077')
  expect(screen.getAllByTestId('window-row')[0]).toHaveTextContent('B2077')
  expect(seen[0]).toContain('/api/overview/adjusted?')
  expect(seen[0]).toContain('bookmarked=true')
})

test('F16-FR-07: nothing is fetched while the window is closed, and Escape closes it', async () => {
  const seen: string[] = []
  stub({ '/api/overview/adjusted': adjustedBody }, seen)
  const onClose = vi.fn()
  const params = new URLSearchParams()
  function Toggle() {
    const [open, setOpen] = useState(false)
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          open
        </button>
        <AdjustedNeedByWindow open={open} onClose={onClose} params={params} />
      </>
    )
  }
  wrap(<Toggle />)
  expect(seen).toEqual([])
  await userEvent.click(screen.getByRole('button', { name: 'open' }))
  await screen.findByText('B2077')
  await userEvent.keyboard('{Escape}')
  expect(onClose).toHaveBeenCalled()
})

const insightsBody = {
  total: 4,
  rows: [
    { row_key: 'a', batch_no: 'B5001', material_no: 'RM1', material_desc: 'One', stage_key: 'qa_release', stage_label: 'QA Release', air_gap_hours: 150, days_gap: 6 },
    { row_key: 'b', batch_no: 'B5002', material_no: 'RM2', material_desc: 'Two', stage_key: 'qa_release', stage_label: 'QA Release', air_gap_hours: 100, days_gap: 4 },
    { row_key: 'c', batch_no: 'B5004', material_no: 'RM3', material_desc: 'Three', stage_key: 'qa_release', stage_label: 'QA Release', air_gap_hours: 50, days_gap: 2 },
    { row_key: 'd', batch_no: 'B5003', material_no: 'RM4', material_desc: 'Four', stage_key: 'qa_release', stage_label: 'QA Release', air_gap_hours: 25, days_gap: 1 },
  ],
}
const reference = { stages: [{ stage_key: 'qa_release', label: 'QA Release' }], air_gap_threshold_hours: 24, terms: {} }

test('F16-FR-09 / AC-05: the insights window title, explanation, worst-first order and Days Gap chips', async () => {
  stub({ '/api/overview/insights': insightsBody, '/api/reference': reference })
  wrap(<InsightsWindow open onClose={vi.fn()} params={new URLSearchParams()} />)
  expect(await screen.findByRole('heading', { name: 'LIMS–ERP Insights — 4 affected batches' })).toBeInTheDocument()
  await screen.findAllByTestId('window-row')
  expect(await screen.findByText('Batches where LIMS is approved but ERP has not received the result. Flagged after 24+ hours — each day erodes the QA Release SLA. Sorted worst-first.')).toBeInTheDocument()
  expect(screen.getAllByRole('columnheader').map((h) => h.textContent?.replace(/[▲▼]/g, ''))).toEqual(['Batch', 'Material', 'Stage', 'Days Gap'])
  const rows = screen.getAllByTestId('window-row')
  expect(rows.map((r) => r.textContent)).toEqual([
    expect.stringContaining('B5001'), expect.stringContaining('B5002'), expect.stringContaining('B5004'), expect.stringContaining('B5003'),
  ])
  expect(within(rows[3]!).getByText('1d')).toHaveAttribute('data-tone', 'green') // B5003 last at 1d
  expect(within(rows[2]!).getByText('2d')).toHaveAttribute('data-tone', 'amber')
  expect(within(rows[1]!).getByText('4d')).toHaveAttribute('data-tone', 'amber')
  expect(within(rows[0]!).getByText('6d')).toHaveAttribute('data-tone', 'red')
})

test('F16-FR-09: the chip thresholds are green < 2, amber 2–5, red > 5', () => {
  expect([1, 2, 5, 6].map(gapTone)).toEqual(['green', 'amber', 'amber', 'red'])
})

test('F17-FR-05: the Expected Deliveries window lists the PO lines with the spec columns and an overdue chip', async () => {
  const seen: string[] = []
  stub(
    {
      '/api/expected-deliveries': {
        count: 2,
        overdue_count: 1,
        mode: 'snapshot',
        rows: [
          { ebeln: '4500000001', ebelp: '00010', material_no: 'RM10010', material_desc: 'Excipient 010', supplier_name: 'Supplier 001', scheduled_date: '2026-10-09', quantity: 500, planned_location: '0100', planned_location_type: 'onsite', overdue: true },
          { ebeln: '4500000002', ebelp: '00010', material_no: 'RM10011', material_desc: 'Buffer 011', supplier_name: 'Supplier 002', scheduled_date: '2026-10-20', quantity: 100, planned_location: '0200', planned_location_type: '3pl', overdue: false },
        ],
      },
    },
    seen,
  )
  wrap(<ExpectedDeliveriesWindow open onClose={vi.fn()} params={new URLSearchParams('type[]=peptide')} />)
  expect(await screen.findByRole('heading', { name: 'Expected Deliveries — 2 open PO lines' })).toBeInTheDocument()
  await screen.findAllByTestId('window-row')
  expect(screen.getAllByRole('columnheader').map((h) => h.textContent?.replace(/[▲▼]/g, ''))).toEqual([
    'PO', 'Line', 'Material', 'Supplier', 'Scheduled', 'Quantity', 'Planned Location', 'Status',
  ])
  const [first, second] = screen.getAllByTestId('window-row')
  expect(within(first!).getByText('4500000001')).toBeInTheDocument()
  expect(within(first!).getByText('9 Oct 2026')).toBeInTheDocument()
  expect(within(first!).getByText('Overdue')).toBeInTheDocument()
  expect(within(second!).getByText('Due')).toBeInTheDocument()
  expect(seen[0]).toContain('/api/expected-deliveries?type%5B%5D=peptide')
})
