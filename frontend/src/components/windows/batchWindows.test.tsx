import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { AdjustNeedsByWindow } from './AdjustNeedsByWindow'
import { InboundWindow } from './InboundWindow'
import { QualityWindow } from './QualityWindow'
import { SampleDataWindow } from './SampleDataWindow'
import { StatusLogWindow } from './StatusLogWindow'

afterEach(() => vi.unstubAllGlobals())

const reference = {
  stages: [
    { stage_key: 'sampling', label: 'Sampling', team: 'Manufacturing' },
    { stage_key: 'qc_testing', label: 'QCL Testing', team: 'QC Lab' },
    { stage_key: 'qa_release', label: 'QA Release', team: 'QA' },
  ],
  reason_codes: [
    { code: 'CAMPAIGN_PULLED_FORWARD', label: 'Campaign pulled forward' },
    { code: 'OTHER', label: 'Other — see notes' },
  ],
  status_options: [
    { key: 'on_track', label: 'On Track', colour: 'green' },
    { key: 'at_risk', label: 'At Risk', colour: 'amber' },
    { key: 'blocked', label: 'Blocked', colour: 'red' },
  ],
  status_reasons: [{ key: 'resource_constraint', label: 'Resource constraint' }],
  site_timezone: 'Europe/Dublin',
  terms: { lims: 'LIMS', erp: 'SAP' },
}

type Calls = { method: string; url: string; body: unknown }[]

function stub(detail: Record<string, unknown>, role = 'planner', extra: (url: string, init?: RequestInit) => Response | null = () => null): Calls {
  const calls: Calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(init.body as string) : null
      calls.push({ method: init?.method ?? 'GET', url, body })
      const custom = extra(url, init)
      if (custom) return custom
      if (url.startsWith('/api/me')) return new Response(JSON.stringify({ user_key: role, display_name: role, role }))
      if (url.startsWith('/api/reference')) return new Response(JSON.stringify(reference))
      if (url.startsWith('/api/rows/')) return new Response(JSON.stringify(detail))
      return new Response('nf', { status: 404 })
    }),
  )
  return calls
}

const base = {
  row_key: 'RM1|B3150|1',
  material_no: 'RM10045',
  material_desc: 'Buffer Salt 012',
  batch_no: 'B3150',
  stage_label: 'QA Release',
  deviations: [],
  changes: [],
  samples: [],
  status_log: [],
  inbound_check: null,
  deviation_light: 'green',
}

const show = (ui: React.ReactElement) => renderWithProviders(<MemoryRouter>{ui}</MemoryRouter>)

// --- W2 Inbound ------------------------------------------------------------------------------------------

const items = [
  { seq: 1, check_code: 'PHYS', check_label: 'Physical evaluation', outcome: 'PASS' },
  { seq: 2, check_code: 'QTYR', check_label: 'Quantity received verification', outcome: 'FAIL' },
  { seq: 3, check_code: 'RESL', check_label: 'Results of analytical work', outcome: 'PENDING' },
]

test('F19-AC-02: a failed inbound check shows Failed, the ERP-term lot number, the deadline, Failed checks: n and the FAIL items in red', async () => {
  stub({ ...base, inbound_check: { prueflos: '10000782', status: 'failed', deadline: '2026-10-11', failed_count: 1, items } })
  show(<InboundWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  expect(await screen.findByRole('heading', { name: 'Inbound — B3150' })).toBeInTheDocument()
  expect(await screen.findByTestId('inbound-result')).toHaveTextContent('Failed')
  expect(screen.getByRole('img', { name: 'Inbound check: red' })).toBeInTheDocument()
  expect(screen.getByText('ERP lot number')).toBeInTheDocument() // the profile term (SAP) comes from the shell's TermsProvider
  expect(screen.getByText('10000782')).toBeInTheDocument()
  expect(screen.getByText('11 Oct 2026')).toBeInTheDocument()
  expect(screen.getByTestId('failed-checks')).toHaveTextContent('Failed checks: 1')
  const failing = within(screen.getByTestId('inbound-items')).getByText('FAIL')
  expect(failing).toHaveClass('text-red-700')
  expect(screen.getByText('Pending')).toBeInTheDocument()
  expect(screen.getByTestId('inbound-verdict')).toHaveTextContent('Failed')
})

test('F19-AC-02: a resolved check shows the amber dot and Completed (Resolved)', async () => {
  stub({ ...base, inbound_check: { prueflos: '1', status: 'resolved', deadline: '2026-10-11', failed_count: 1, items } })
  show(<InboundWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  expect(await screen.findByTestId('inbound-result')).toHaveTextContent('Completed (Resolved)')
  expect(screen.getByRole('img', { name: 'Inbound check: amber' })).toBeInTheDocument()
})

test('F19-FR-01: no inbound check shows the grey No status state and the one-line explanation', async () => {
  stub(base)
  show(<InboundWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  expect(await screen.findByTestId('inbound-result')).toHaveTextContent('No status')
  expect(screen.getByTestId('inbound-none')).toHaveTextContent('No inbound check recorded.')
})

// --- W3 Quality ------------------------------------------------------------------------------------------

const deviation = (n: number, severity: string, status: string, opened: string) => ({
  deviation_no: `DEV-00000${n}`,
  title: `Title ${n}`,
  severity,
  status,
  opened_on: opened,
  causal_factor: 'Carrier handling',
  root_cause_category: 'Transport',
  description: `Description ${n}`,
  investigation_summary: n === 1 ? 'Handled with the carrier.' : null,
  owner: 'QA',
})

test('F19-AC-03: B3150 shows Red, 1 open deviation, Open Deviations (1) with a Major card, and the severity pills filter it', async () => {
  stub({
    ...base,
    deviation_light: 'red',
    deviations: [deviation(1, 'major', 'open', '2026-10-08'), deviation(2, 'minor', 'closed', '2026-09-01'), deviation(3, 'moderate', 'closed', '2026-09-20')],
  })
  show(<QualityWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  expect(await screen.findByTestId('quality-rating')).toHaveTextContent('Red, 1 open deviation')
  const tabs = screen.getAllByRole('tab').map((tab) => tab.textContent)
  expect(tabs).toEqual(['Open Deviations (1)', 'Closed / Cancelled (2)', 'Changes (0)'])
  const card = screen.getByTestId('deviation-card')
  expect(within(card).getByTestId('severity-badge')).toHaveTextContent('Major')
  expect(card).toHaveTextContent('Ref: DEV-000001')
  expect(card).toHaveTextContent('Causal Factor: Carrier handling')
  expect(card).toHaveTextContent('Root Cause: Transport')
  expect(card).toHaveTextContent('Description: Description 1')
  expect(card).toHaveTextContent('Investigation Summary: Handled with the carrier.')

  await userEvent.click(screen.getByRole('button', { name: 'Minor' })) // no minor open deviation
  expect(screen.queryByTestId('deviation-card')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'ALL' }))
  await userEvent.click(screen.getByRole('tab', { name: /Closed/ }))
  expect(screen.getAllByTestId('deviation-card')).toHaveLength(2)
  await userEvent.click(screen.getByRole('button', { name: 'Moderate' }))
  expect(screen.getAllByTestId('deviation-card')).toHaveLength(1)
  expect(screen.getByTestId('deviation-card')).toHaveAttribute('data-severity', 'moderate')
})

test('F19-FR-01: the sort puts the newest first or the oldest first, and collapse all hides the details', async () => {
  stub({ ...base, deviation_light: 'red', deviations: [deviation(1, 'major', 'open', '2026-10-08'), deviation(2, 'minor', 'open', '2026-10-10')] })
  show(<QualityWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  await screen.findByTestId('quality-rating')
  const order = () => screen.getAllByTestId('deviation-card').map((card) => card.textContent?.match(/DEV-\d+/)?.[0])
  expect(order()).toEqual(['DEV-000002', 'DEV-000001'])
  await userEvent.selectOptions(screen.getByLabelText('Sort'), 'oldest')
  expect(order()).toEqual(['DEV-000001', 'DEV-000002'])
  await userEvent.click(screen.getByRole('button', { name: 'Collapse all' }))
  expect(screen.queryByText(/Causal Factor/)).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Expand all' }))
  expect(screen.getAllByText(/Causal Factor/)).toHaveLength(2)
})

test('F19-AC-03: a green batch with a linked change control shows Changes (1) with current and proposed state', async () => {
  stub({ ...base, changes: [{ cc_no: 'CC-000007', title: 'Update the storage specification', status: 'approved', current_state: 'Store at 2-8 C', proposed_state: 'Store at 2-25 C', effective_on: '2026-11-01' }] })
  show(<QualityWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  expect(await screen.findByTestId('quality-rating')).toHaveTextContent('Green, 0 open deviations')
  await userEvent.click(screen.getByRole('tab', { name: 'Changes (1)' }))
  const card = screen.getByTestId('change-card')
  expect(card).toHaveTextContent('Ref: CC-000007')
  expect(card).toHaveTextContent('Approved')
  expect(card).toHaveTextContent('Store at 2-8 C → Store at 2-25 C')
  expect(card).toHaveTextContent('Effective 1 Nov 2026')
})

// --- W4 Status log ---------------------------------------------------------------------------------------

const entry = (id: number, status: string | null, comment: string) => ({
  id, row_key: 'RM1|B3150|1', status, team: status ? 'QC Lab' : null, reason_code: status ? 'resource_constraint' : null,
  comment, author_user_key: 'quinn', at: '2026-10-12T07:00:00Z',
})

test('F19-AC-04: Quinn adds At Risk / QC Lab / Resource constraint with a comment; the button stays disabled until there is a comment', async () => {
  const calls = stub({ ...base, status_log: [] }, 'quinn')
  show(<StatusLogWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  expect(await screen.findByRole('heading', { name: 'Status Log — B3150' })).toBeInTheDocument()
  await waitFor(() => expect(screen.getByLabelText('Comment')).toBeEnabled())
  expect(screen.getByTestId('status-subtitle')).toHaveTextContent('RM10045 · QA Release')
  const add = screen.getByRole('button', { name: 'Add Status Update' })
  expect(add).toBeDisabled()
  await userEvent.selectOptions(screen.getByLabelText('Status'), 'at_risk')
  await userEvent.selectOptions(screen.getByLabelText('Area / Team'), 'QC Lab')
  await userEvent.selectOptions(screen.getByLabelText('Reason'), 'resource_constraint')
  expect(add).toBeDisabled() // no comment yet
  await userEvent.type(screen.getByLabelText('Comment'), 'Waiting for a free analyst')
  await userEvent.click(add)
  await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
  expect(calls.find((c) => c.method === 'POST')).toMatchObject({
    url: '/api/rows/RM1%7CB3150%7C1/status-log',
    body: { status: 'at_risk', team: 'QC Lab', reason_code: 'resource_constraint', comment: 'Waiting for a free analyst' },
  })
})

test('F19-AC-04: the latest entry tops the Latest tab and History (n) appears only with a second entry, newest first', async () => {
  stub({ ...base, status_log: [entry(2, 'at_risk', 'Second update'), entry(1, 'on_track', 'First update')] }, 'quinn')
  show(<StatusLogWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  const latest = await screen.findByTestId('status-latest')
  expect(within(latest).getByTestId('status-entry-comment')).toHaveTextContent('Second update')
  await waitFor(() => expect(within(latest).getByTestId('status-entry-status')).toHaveTextContent('At Risk'))
  expect(await within(latest).findByText('Resource constraint')).toHaveClass('italic')
  expect(within(latest).getByText(/quinn · 12\/10\/2026 08:00/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('tab', { name: 'History (2)' }))
  const history = screen.getByTestId('status-history')
  expect(within(history).getAllByTestId('status-entry-comment').map((c) => c.textContent)).toEqual(['Second update', 'First update'])
  await userEvent.click(screen.getByRole('button', { name: /Newest first/ }))
  expect(within(history).getAllByTestId('status-entry-comment').map((c) => c.textContent)).toEqual(['First update', 'Second update'])
})

test('F19-FR-05: a window with one entry has no History tab; a comment-only entry shows without a dot', async () => {
  stub({ ...base, status_log: [entry(1, null, 'Chased the supplier')] }, 'pat')
  show(<StatusLogWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  expect(await screen.findByTestId('status-latest')).toHaveTextContent('Chased the supplier')
  expect(screen.queryByRole('tab', { name: /History/ })).not.toBeInTheDocument()
  expect(screen.queryByTestId('status-entry-status')).not.toBeInTheDocument()
})

test('F19-AC-04: as Sam (viewer) the form is disabled with the read-only tooltip', async () => {
  stub({ ...base, status_log: [] }, 'viewer')
  show(<StatusLogWindow rowKey="RM1|B3150|1" onClose={vi.fn()} />)
  await screen.findByRole('heading', { name: 'Status Log — B3150' })
  await waitFor(() => expect(screen.getByLabelText('Comment')).toBeDisabled())
  expect(screen.getByLabelText('Status')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Add Status Update' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Add Status Update' })).toHaveAttribute('title', 'Read-only role')
})

// --- W5 Sample data --------------------------------------------------------------------------------------

test('F19-AC-05: Sample Data lists the samples with a pill per status; clicking a Sample ID copies it and toasts Copied', async () => {
  const written: string[] = []
  vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText: async (text: string) => void written.push(text) } })
  stub({ ...base, batch_no: 'B1042', samples: [{ sample_id: 'S-0000007', status: 'in_progress', collected_date: '2026-10-05', approved_at: null }] })
  show(<SampleDataWindow rowKey="RM1|B1042|1" onClose={vi.fn()} />)
  expect(await screen.findByRole('heading', { name: 'Sample Data — B1042 (1 sample)' })).toBeInTheDocument()
  expect(screen.getByText('LIMS sample records for this batch. Click a Sample ID to copy it.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'All (1)' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Received (1)' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Approved (0)' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Rejected/ })).not.toBeInTheDocument() // only when any
  await userEvent.click(screen.getByRole('button', { name: 'S-0000007' }))
  await waitFor(() => expect(written).toEqual(['S-0000007']))
  expect(await screen.findByText('Copied')).toBeInTheDocument()
})

test('F19-AC-05: with several statuses the pills count each, Rejected appears, and a pill filters the table', async () => {
  const samples = [
    { sample_id: 'S-1', status: 'rejected', collected_date: '2026-10-01', approved_at: null },
    { sample_id: 'S-2', status: 'approved', collected_date: '2026-10-05', approved_at: '2026-10-09T07:00:00Z' },
    { sample_id: 'S-3', status: 'registered', collected_date: '2026-10-06', approved_at: null },
  ]
  stub({ ...base, batch_no: 'B1042', samples })
  show(<SampleDataWindow rowKey="RM1|B1042|1" onClose={vi.fn()} />)
  expect(await screen.findByRole('button', { name: 'All (3)' })).toBeInTheDocument()
  for (const name of ['Received (1)', 'Approved (1)', 'Rejected (1)']) expect(screen.getByRole('button', { name })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Approved (1)' }))
  const rows = screen.getAllByTestId('window-row')
  expect(rows).toHaveLength(1)
  expect(rows[0]).toHaveTextContent('S-2')
})

// --- W6 Adjust Needs-by ----------------------------------------------------------------------------------

const plan = (compressed: boolean, deadlines: Record<string, string>) => ({
  expected_completion: '2026-10-14', rag: 'amber', compressed, compression_ratio: compressed ? '0.875' : null,
  effective_slas: {}, must_complete_by: deadlines, days_remaining: 2, late: false,
})
const b2077 = {
  ...base,
  row_key: 'RM1|B2077|1',
  batch_no: 'B2077',
  material_no: 'RM10031',
  material_desc: 'Excipient 017',
  system_need_by_locked: '2026-12-03',
  adjusted_need_by_date: null,
  adjusted_reason_code: null,
  expedite: false,
}

function needByApi(url: string, init?: RequestInit): Response | null {
  const body = init?.body ? JSON.parse(init.body as string) : null
  if (url.includes('/need-by/preview'))
    return new Response(JSON.stringify({ current: plan(false, {}), preview: body.adjusted_date ? plan(true, { sampling: '2026-10-14', qc_testing: '2026-11-20', qa_release: '2026-11-26' }) : plan(false, {}) }))
  if (url.endsWith('/need-by') && init?.method === 'PUT') return new Response('{}')
  return null
}

test('F19-AC-06 (act 5): B2077 set to 26 Nov shows −7d (pulled forward) in red and the three compressed deadlines; Save needs a reason', async () => {
  const calls = stub(b2077, 'planner', needByApi)
  const onClose = vi.fn()
  show(<AdjustNeedsByWindow rowKey="RM1|B2077|1" onClose={onClose} />)
  expect(await screen.findByRole('heading', { name: 'Adjust Needs-by Date — B2077' })).toBeInTheDocument()
  expect(screen.getByTestId('system-date-box')).toHaveTextContent('3 Dec 2026')
  await waitFor(() => expect(screen.getByLabelText('New Adjusted Date')).toBeEnabled())
  const save = screen.getByRole('button', { name: 'Save' })
  expect(save).toBeDisabled()
  await userEvent.type(screen.getByLabelText('New Adjusted Date'), '2026-11-26')
  const delta = screen.getByTestId('needby-delta')
  expect(delta).toHaveTextContent('−7d (pulled forward)')
  expect(delta).toHaveAttribute('data-tone', 'red')
  expect(save).toBeDisabled() // a date needs a reason
  await userEvent.selectOptions(screen.getByLabelText('Reason for Change'), 'CAMPAIGN_PULLED_FORWARD')
  expect(await screen.findByText('Compressed stage deadlines (preview)')).toBeInTheDocument()
  const deadlines = screen.getByTestId('preview-deadlines')
  expect(deadlines).toHaveTextContent('Sampling: 14 Oct 2026')
  expect(deadlines).toHaveTextContent('QCL Testing: 20 Nov 2026')
  expect(deadlines).toHaveTextContent('QA Release: 26 Nov 2026')
  expect(screen.getByText(/the scheduled pipeline run remains authoritative/)).toBeInTheDocument()
  expect(calls.some((c) => c.method === 'PUT')).toBe(false) // previewing writes nothing
  expect(save).toBeEnabled()
  await userEvent.click(save)
  await waitFor(() => expect(onClose).toHaveBeenCalled())
  expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ adjusted_date: '2026-11-26', reason_code: 'CAMPAIGN_PULLED_FORWARD', expedite: false, note: null })
})

test('F19-FR-06: pushing the date back reads +3d (pushed back) in green, and Other — see notes needs a note before Save', async () => {
  stub(b2077, 'planner', needByApi)
  show(<AdjustNeedsByWindow rowKey="RM1|B2077|1" onClose={vi.fn()} />)
  await waitFor(() => expect(screen.getByLabelText('New Adjusted Date')).toBeEnabled())
  await userEvent.type(screen.getByLabelText('New Adjusted Date'), '2026-12-06')
  expect(screen.getByTestId('needby-delta')).toHaveTextContent('+3d (pushed back)')
  expect(screen.getByTestId('needby-delta')).toHaveAttribute('data-tone', 'green')
  await userEvent.selectOptions(screen.getByLabelText('Reason for Change'), 'OTHER')
  const save = screen.getByRole('button', { name: 'Save' })
  expect(save).toBeDisabled()
  expect(screen.getByText('Notes (required)')).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText('Notes'), 'Agreed with planning')
  expect(save).toBeEnabled()
})

test('F19-FR-01: an existing override offers Clear override, and the expedite box is part of the same Save', async () => {
  const calls = stub({ ...b2077, adjusted_need_by_date: '2026-11-26', adjusted_reason_code: 'CAMPAIGN_PULLED_FORWARD' }, 'admin', needByApi)
  show(<AdjustNeedsByWindow rowKey="RM1|B2077|1" onClose={vi.fn()} />)
  await userEvent.click(await screen.findByRole('checkbox', { name: /Expedite — tag this batch as expedited/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Clear override' }))
  await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
  expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ adjusted_date: null, reason_code: null, expedite: true, note: null })
})

test('F19-FR-01: for a viewer every control of the window is disabled with the read-only tooltip', async () => {
  stub(b2077, 'viewer', needByApi)
  show(<AdjustNeedsByWindow rowKey="RM1|B2077|1" onClose={vi.fn()} />)
  await screen.findByRole('heading', { name: 'Adjust Needs-by Date — B2077' })
  await waitFor(() => expect(screen.getByLabelText('New Adjusted Date')).toBeDisabled())
  expect(screen.getByLabelText('Reason for Change')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('title', 'Read-only role')
})

test('F19-FR-01: Escape closes a window and a missing batch says so', async () => {
  const onClose = vi.fn()
  stub(base, 'planner', (url) => (url.startsWith('/api/rows/') ? new Response(JSON.stringify({ detail: 'unknown row' }), { status: 404 }) : null))
  show(<QualityWindow rowKey="NOPE|B0|0" onClose={onClose} />)
  expect(await screen.findByText(/Batch not found: NOPE\|B0\|0/)).toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  expect(onClose).toHaveBeenCalled()
})


test('F19-FR-01: focus moves into the window and returns to the trigger when it closes', async () => {
  stub(base)
  function Harness() {
    const [open, setOpen] = useState(false)
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          trigger
        </button>
        {open && <QualityWindow rowKey="RM1|B3150|1" onClose={() => setOpen(false)} />}
      </>
    )
  }
  show(<Harness />)
  const trigger = screen.getByRole('button', { name: 'trigger' })
  await userEvent.click(trigger)
  const dialog = await screen.findByRole('dialog')
  expect(dialog.contains(document.activeElement)).toBe(true) // focus is inside the window
  await userEvent.tab()
  await userEvent.tab()
  await userEvent.tab()
  expect(dialog.contains(document.activeElement)).toBe(true) // and trapped there
  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(trigger).toHaveFocus())
})
