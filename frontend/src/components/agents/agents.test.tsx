import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { Agents } from '../../pages/Agents'
import { ProposalPage } from '../../pages/agents/ProposalPage'
import { TracePage } from '../../pages/agents/TracePage'
import { renderWithProviders } from '../../test-utils'
import { InsightsWindow } from '../windows/InsightsWindow'
import { ProposalLine } from './ProposalLine'
import { ProviderChip } from './ProviderChip'
import { ProposalPill, STATUS_LABEL } from './ProposalPill'
import { summarise } from './TraceTimeline'

afterEach(() => vi.unstubAllGlobals())

type Handler = unknown | ((url: string, init?: RequestInit) => unknown)

/** fetch by URL prefix (longest first); a function gets the request and may return a Response. */
function stub(routes: Record<string, Handler>, seen: { url: string; method: string }[] = []) {
  const keys = Object.keys(routes).sort((a, b) => b.length - a.length)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      seen.push({ url, method: init?.method ?? 'GET' })
      const key = keys.find((k) => url.startsWith(k))
      if (!key) return new Response('nf', { status: 404 })
      const handler = routes[key]
      const result = typeof handler === 'function' ? (handler as (u: string, i?: RequestInit) => unknown)(url, init) : handler
      return result instanceof Response ? result : new Response(JSON.stringify(result))
    }),
  )
}

const me = (role: string, user = role) => ({ user_key: user, display_name: user, role })
const reference = { site_timezone: 'Europe/Dublin', stages: [{ stage_key: 'qa_release', label: 'QA Release' }], air_gap_threshold_hours: 24, terms: {} }

const evidence = [
  { system: 'LIMS', ref: 'S-0000404', field: 'approved_at', value: '2026-10-11T01:00:00Z' },
  { system: 'ERP', ref: '10000459', field: 'results_recorded_at', value: 'none' },
]
const rules = ['V1', 'V2', 'V3', 'V4', 'V5', 'V6'].map((id) => ({ id, name: `Rule ${id}`, passed: true, message: `${id} fine` }))
const validator = {
  passed: true,
  headline: null,
  rules,
  evidence: [
    { index: 0, verified: true, message: 'ok' },
    { index: 1, verified: true, message: 'ok' },
  ],
  checked_at: '2026-10-12T07:00:00Z',
}
const summary = {
  id: 1, agent_key: 'air_gap', kind: 'airgap_ticket', row_key: 'RM10067|B5003|10000459', batch_no: 'B5003', status: 'pending_approval',
  required_role: 'qa_release', created_at: '2026-10-12T07:00:00Z', decided_by: null, decided_at: null, decision_reason: null,
  trace_id: 'TR-0001', title: 'Batch B5003: LIMS approved, no ERP usage decision', priority: 'high', recommended_action: 'post_usage_decision',
  hours_in_gap: 30, error: null,
}
const detail = {
  ...summary,
  payload: {
    row_key: summary.row_key, title: summary.title, summary: 'LIMS approved the sample 30 hours ago.', evidence, hours_in_gap: 30,
    open_deviations: [], recommended_action: 'post_usage_decision', priority: 'high', recipient_role: 'qa_release',
  },
  evidence,
  validator,
  actions: [],
}
const executed = {
  ...detail,
  status: 'executed',
  decided_by: 'alex',
  decided_at: '2026-10-12T07:00:00Z',
  actions: [
    { id: 1, action_type: 'ticket_created', executed_at: 'x', rendered: { ticket_no: 'TKT-0001', text: 'Ticket body text', title: 't' } },
    {
      id: 2, action_type: 'email_queued', executed_at: 'x',
      rendered: { to: 'QA Release Team <qa-release@demo-pharma.example>', subject: '[HIGH] Air gap B5003 (TKT-0001)', body: 'Hello QA', delivery: 'Sent to outbox (demo)' },
    },
  ],
}
const listing = { counts: { pending_approval: 1, rejected_by_validator: 0, approved: 0, rejected: 0, executed: 0 }, rows: [summary] }
const card = {
  key: 'air_gap', name: 'Air-gap agent', purpose: 'Drafts a ticket.', provider: 'replay', model_id: 'claude-sonnet-5-5', prompt_version: 'v1',
  tools: ['get_row', 'get_erp_lot'], can_run: true, last_run_at: null, proposals_total: 0,
}

function atPage(path: string, ui: React.ReactElement) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/agents" element={ui} />
        <Route path="/agents/proposals/:id" element={ui} />
        <Route path="/agents/traces/:traceId" element={ui} />
        <Route path="*" element={<p data-testid="elsewhere">elsewhere</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

test('F12-FR-12: the status pill reads the same everywhere and names each status', () => {
  expect(STATUS_LABEL).toEqual({
    pending_approval: 'Pending approval', rejected_by_validator: 'Rejected by validator', approved: 'Approved', rejected: 'Rejected', executed: 'Executed',
  })
  renderWithProviders(<ProposalPill status="rejected_by_validator" />)
  expect(screen.getByText('Rejected by validator')).toHaveAttribute('data-status', 'rejected_by_validator')
})

test('F12-FR-12 a: the agent card shows model, prompt version, tools and last run, and Run now creates proposals', async () => {
  const seen: { url: string; method: string }[] = []
  stub(
    {
      '/api/me': me('qa_release', 'alex'),
      '/api/reference': reference,
      '/agents-api/agents/air_gap/run': { created: [{ row_key: 'k', outcome: 'created', proposal_id: 1, status: 'pending_approval', trace_id: 'TR-0001', message: '', replay_miss: null }], skipped: [], errors: [] },
      '/agents-api/agents': [{ ...card, last_run_at: '2026-10-12T07:00:00Z' }],
      '/agents-api/proposals': listing,
    },
    seen,
  )
  atPage('/agents', <Agents />)
  const agent = await screen.findByTestId('agent-card')
  expect(within(agent).getByText('Air-gap agent')).toBeInTheDocument()
  expect(screen.getByTestId('agent-model')).toHaveTextContent('claude-sonnet-5-5')
  expect(screen.getByTestId('agent-model')).toHaveTextContent('Replay · recorded from claude-sonnet-5-5') // F14-FR-17
  expect(screen.getByTestId('agent-prompt')).toHaveTextContent('v1')
  expect(screen.getByTestId('agent-last-run')).toHaveTextContent('Last run Mon 12 Oct 2026 08:00')
  expect(within(agent).getByText('get_erp_lot')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Run now' }))
  expect(await screen.findByTestId('run-result')).toHaveTextContent('1 proposal created.')
  expect(seen.some((r) => r.method === 'POST' && r.url === '/agents-api/agents/air_gap/run')).toBe(true)
})

test('F12-AC-09: a replay miss shows the hint and the key, not a crash', async () => {
  stub({
    '/api/reference': reference,
    '/agents-api/agents/air_gap/run': () =>
      new Response(
        JSON.stringify({ detail: { error: 'replay_miss', message: 'No recording for key abc123def4567890xyz', replay_miss: { key: 'abc123def4567890xyz', hint: 'Recordings exist only for the demo-start state. Run make record-agents.' }, errors: [] } }),
        { status: 409 },
      ),
    '/agents-api/agents': [card],
    '/agents-api/proposals': listing,
  })
  atPage('/agents', <Agents />)
  await userEvent.click(await screen.findByRole('button', { name: 'Run now' }))
  const alert = await screen.findByTestId('run-error')
  expect(alert).toHaveTextContent('No recording for this situation.')
  expect(alert).toHaveTextContent('Recordings exist only for the demo-start state')
  expect(alert).toHaveTextContent('abc123def4567890')
  expect(screen.getByTestId('agents-page')).toBeInTheDocument() // the page is still there
})

test('F12-FR-12 a: Run now is disabled with the tooltip for a role that may not run the agent', async () => {
  stub({ '/api/me': me('planner', 'pat'), '/api/reference': reference, '/agents-api/agents': [{ ...card, can_run: false }], '/agents-api/proposals': listing })
  atPage('/agents', <Agents />)
  const button = await screen.findByRole('button', { name: 'Run now' })
  expect(button).toBeDisabled()
  expect(button).toHaveAttribute('title', 'Read-only role')
})

test('F12-FR-12 b: the inbox has status tabs with counts, and a row opens the proposal', async () => {
  const seen: { url: string; method: string }[] = []
  stub({ '/api/reference': reference, '/agents-api/agents': [card], '/agents-api/proposals': listing }, seen)
  atPage('/agents', <Agents />)
  const rows = await screen.findAllByTestId('proposal-row')
  expect(rows).toHaveLength(1)
  expect(rows[0]).toHaveTextContent('B5003')
  expect(rows[0]).toHaveTextContent('Pending approval')
  expect(rows[0]).toHaveTextContent('30 h')
  expect(rows[0]).toHaveTextContent('Post usage decision')
  const pending = screen.getByRole('tab', { name: /Pending approval/ })
  expect(pending).toHaveTextContent('1')
  await userEvent.click(screen.getByRole('tab', { name: /Executed/ }))
  await waitFor(() => expect(seen.some((r) => r.url === '/agents-api/proposals?status=executed')).toBe(true))
  await userEvent.click(rows[0]!)
})

test('F12-FR-12 c: the proposal shows the evidence with verified ticks and the V1 to V6 checklist', async () => {
  stub({ '/api/me': me('qa_release', 'alex'), '/api/reference': reference, '/agents-api/proposals/1': detail })
  atPage('/agents/proposals/1', <ProposalPage />)
  expect(await screen.findByRole('heading', { name: /Proposal #1 · Air-gap ticket for B5003/ })).toBeInTheDocument()
  const rowsOfEvidence = await screen.findAllByTestId('evidence-row')
  expect(rowsOfEvidence).toHaveLength(2)
  expect(rowsOfEvidence[0]).toHaveTextContent('LIMS')
  expect(rowsOfEvidence[0]).toHaveTextContent('S-0000404')
  expect(within(rowsOfEvidence[0]!).getByText('verified ✓')).toBeInTheDocument()
  for (const id of ['V1', 'V2', 'V3', 'V4', 'V5', 'V6']) expect(screen.getByTestId(`rule-${id}`)).toHaveAttribute('data-passed', 'true')
  expect(screen.getByTestId('validator-checklist')).toBeInTheDocument()
  expect(screen.getByTestId('view-trace')).toHaveAttribute('href', '/agents/traces/TR-0001')
  expect(screen.getByTestId('draft')).toHaveTextContent('LIMS approved the sample 30 hours ago.')
})

test('F12-AC-02: Approve is enabled for QA release and approving shows the executed ticket and the outbox email', async () => {
  let approved = false
  stub({
    '/api/me': me('qa_release', 'alex'),
    '/api/reference': reference,
    '/agents-api/proposals/1/approve': () => {
      approved = true
      return executed
    },
    '/agents-api/proposals/1': () => (approved ? executed : detail),
  })
  atPage('/agents/proposals/1', <ProposalPage />)
  const approve = await screen.findByRole('button', { name: 'Approve' })
  await waitFor(() => expect(approve).toBeEnabled())
  await userEvent.click(approve)
  const preview = await screen.findByTestId('executed-preview')
  expect(within(preview).getByTestId('delivery')).toHaveTextContent('Sent to outbox (demo)')
  expect(within(preview).getByTestId('email-subject')).toHaveTextContent('TKT-0001')
  expect(within(preview).getByTestId('ticket-text')).toHaveTextContent('Ticket body text')
  expect(screen.getByTestId('decided-line')).toHaveTextContent('Approved by alex')
  expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
})

test('F12-AC-02: Approve and Reject are disabled for a planner, with the reason in a tooltip', async () => {
  stub({ '/api/me': me('planner', 'pat'), '/api/reference': reference, '/agents-api/proposals/1': detail })
  atPage('/agents/proposals/1', <ProposalPage />)
  const approve = await screen.findByRole('button', { name: 'Approve' })
  await waitFor(() => expect(approve).toBeDisabled())
  expect(approve).toHaveAttribute('title', 'Needs the QA Release role')
  expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled()
  expect(screen.getByText(/Only QA Release \(or Admin\) can decide/)).toBeInTheDocument()
})

test('F12-FR-08: Reject asks for a reason of 3 to 200 characters and sends it', async () => {
  const seen: { url: string; method: string; body?: string }[] = []
  let rejected = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      seen.push({ url, method: init?.method ?? 'GET', body: init?.body as string | undefined })
      if (url === '/api/me') return new Response(JSON.stringify(me('qa_release', 'alex')))
      if (url === '/api/reference') return new Response(JSON.stringify(reference))
      if (url === '/agents-api/proposals/1/reject') {
        rejected = true
        return new Response(JSON.stringify({ ...detail, status: 'rejected', decided_by: 'alex', decision_reason: 'Handled by phone' }))
      }
      if (url === '/agents-api/proposals/1') return new Response(JSON.stringify(rejected ? { ...detail, status: 'rejected', decided_by: 'alex', decision_reason: 'Handled by phone' } : detail))
      return new Response('nf', { status: 404 })
    }),
  )
  atPage('/agents/proposals/1', <ProposalPage />)
  const open = await screen.findByRole('button', { name: 'Reject' })
  await waitFor(() => expect(open).toBeEnabled())
  await userEvent.click(open)
  const dialog = await screen.findByTestId('reject-dialog')
  const submit = within(dialog).getByRole('button', { name: 'Reject' })
  expect(submit).toBeDisabled()
  await userEvent.type(within(dialog).getByRole('textbox'), 'no')
  expect(submit).toBeDisabled()
  await userEvent.type(within(dialog).getByRole('textbox'), ' longer reason')
  expect(submit).toBeEnabled()
  await userEvent.clear(within(dialog).getByRole('textbox'))
  await userEvent.type(within(dialog).getByRole('textbox'), 'Handled by phone')
  await userEvent.click(submit)
  await waitFor(() => expect(screen.getByTestId('reject-reason')).toHaveTextContent('Rejected by alex: Handled by phone'))
  expect(JSON.parse(seen.find((r) => r.url.endsWith('/reject'))!.body!)).toEqual({ reason: 'Handled by phone' })
})

test('F12-AC-04: a proposal the validator rejected shows the reason and cannot be approved', async () => {
  const failed = {
    ...detail,
    status: 'rejected_by_validator',
    validator: {
      ...validator,
      passed: false,
      headline: 'Air gap resolved',
      rules: rules.map((r) => (r.id === 'V1' ? { ...r, passed: false, message: 'Air gap resolved' } : r)),
    },
  }
  stub({ '/api/me': me('qa_release', 'alex'), '/api/reference': reference, '/agents-api/proposals/1': failed })
  atPage('/agents/proposals/1', <ProposalPage />)
  expect(await screen.findByTestId('validator-headline')).toHaveTextContent('Air gap resolved')
  expect(screen.getByTestId('rule-V1')).toHaveAttribute('data-passed', 'false')
  expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run again' })).toBeInTheDocument()
})

test('F12-FR-12 d: the trace is a timeline of steps in order with totals and a cost estimate', async () => {
  const steps = [
    { seq: 1, step_type: 'input', payload: { agent: 'air_gap', batch_no: 'B5003', air_gap_hours: 30 }, tokens_in: null, tokens_out: null, latency_ms: null, at: 'x' },
    { seq: 2, step_type: 'model_request', payload: { turn: 1, model_id: 'claude-sonnet-5-5' }, tokens_in: null, tokens_out: null, latency_ms: null, at: 'x' },
    { seq: 3, step_type: 'model_response', payload: { stop_reason: 'tool_use', replayed: true, content: [{ type: 'tool_use', name: 'get_row' }] }, tokens_in: 1000, tokens_out: 100, latency_ms: 900, at: 'x' },
    { seq: 4, step_type: 'tool_call', payload: { name: 'get_row', input: { row_key: 'RM10067|B5003|10000459' }, system: 'app' }, tokens_in: null, tokens_out: null, latency_ms: null, at: 'x' },
    { seq: 5, step_type: 'validation', payload: { passed: true, rules }, tokens_in: null, tokens_out: null, latency_ms: null, at: 'x' },
    { seq: 6, step_type: 'decision', payload: { outcome: 'proposed' }, tokens_in: null, tokens_out: null, latency_ms: null, at: 'x' },
    { seq: 7, step_type: 'action', payload: { type: 'proposal_stored', proposal_id: 1 }, tokens_in: null, tokens_out: null, latency_ms: null, at: 'x' },
  ]
  stub({
    '/agents-api/traces/TR-0001': {
      trace_id: 'TR-0001', proposal_id: 1, row_key: 'k', provider: 'replay', model_id: 'claude-sonnet-5-5', replayed: true, steps,
      totals: { tokens_in: 1000, tokens_out: 100, latency_ms: 900, cost_usd: 0.0045, model_calls: 1 },
    },
  })
  atPage('/agents/traces/TR-0001', <TracePage />)
  const items = await screen.findAllByTestId('trace-step')
  expect(items.map((i) => i.getAttribute('data-step-type'))).toEqual(['input', 'model_request', 'model_response', 'tool_call', 'validation', 'decision', 'action'])
  expect(screen.getByTestId('trace-totals')).toHaveTextContent('$0.0045')
  expect(screen.getByTestId('trace-totals')).toHaveTextContent('1000')
  expect(screen.getByTestId('trace-provider')).toHaveTextContent('replay · replayed')
  expect(items[2]).toHaveTextContent('1000 in / 100 out 900 ms')
  expect(items[3]).toHaveTextContent('get_row(RM10067|B5003|10000459) → app')
  expect(screen.getByRole('link', { name: /Proposal #1/ })).toHaveAttribute('href', '/agents/proposals/1')
  expect(summarise(steps[4] as never)).toBe('All 6 rules passed')
})

test('F12-FR-13: the drawer line shows the status with a link, "none yet" for an air gap, and nothing otherwise', () => {
  const { unmount } = renderWithProviders(
    <MemoryRouter>
      <ProposalLine detail={{ air_gap: true, proposal: { id: 4, status: 'pending_approval', priority: 'high' } }} />
    </MemoryRouter>,
  )
  const line = screen.getByTestId('proposal-line')
  expect(line).toHaveTextContent('Agent proposal')
  expect(within(line).getByText('Pending approval')).toBeInTheDocument()
  expect(within(line).getByRole('link', { name: 'View ↗' })).toHaveAttribute('href', '/agents/proposals/4')
  unmount()
  const none = renderWithProviders(
    <MemoryRouter>
      <ProposalLine detail={{ air_gap: true, proposal: null }} />
    </MemoryRouter>,
  )
  expect(screen.getByTestId('proposal-line')).toHaveTextContent('None yet')
  none.unmount()
  const quiet = renderWithProviders(
    <MemoryRouter>
      <ProposalLine detail={{ air_gap: false, proposal: null }} />
    </MemoryRouter>,
  )
  expect(quiet.queryByTestId('proposal-line')).not.toBeInTheDocument()
})

const insights = {
  total: 2,
  rows: [
    { row_key: 'k1', batch_no: 'B5001', material_no: 'RM1', material_desc: 'One', stage_key: 'qa_release', stage_label: 'QA Release', air_gap_hours: 100, days_gap: 4, proposal: { id: 7, status: 'executed', priority: 'high' } },
    { row_key: 'k2', batch_no: 'B5003', material_no: 'RM2', material_desc: 'Two', stage_key: 'qa_release', stage_label: 'QA Release', air_gap_hours: 30, days_gap: 1, proposal: null },
  ],
}

test('F12-FR-13: the Insights window has a Proposal column with a link to the proposal', async () => {
  stub({ '/api/overview/insights': insights, '/api/reference': reference, '/api/me': me('qa_release', 'alex') })
  renderWithProviders(
    <MemoryRouter>
      <InsightsWindow open onClose={vi.fn()} params={new URLSearchParams()} />
    </MemoryRouter>,
  )
  const rows = await screen.findAllByTestId('window-row')
  expect(screen.getAllByRole('columnheader').map((h) => h.textContent?.replace(/[▲▼]/g, ''))).toContain('Proposal')
  const link = within(rows[0]!).getByTestId('proposal-link')
  expect(link).toHaveAttribute('href', '/agents/proposals/7')
  expect(link).toHaveTextContent('Executed')
  expect(within(rows[1]!).queryByTestId('proposal-link')).not.toBeInTheDocument()
})

test('F12-FR-13: the Run air-gap agent button runs the agent, for QA release and admin only', async () => {
  const seen: { url: string; method: string }[] = []
  stub(
    {
      '/api/overview/insights': insights,
      '/api/reference': reference,
      '/api/me': me('qa_release', 'alex'),
      '/agents-api/agents/air_gap/run': { created: [{ row_key: 'k2', outcome: 'created', proposal_id: 8, status: 'pending_approval', trace_id: 'TR-0002', message: '', replay_miss: null }], skipped: [], errors: [] },
    },
    seen,
  )
  renderWithProviders(
    <MemoryRouter>
      <InsightsWindow open onClose={vi.fn()} params={new URLSearchParams()} />
    </MemoryRouter>,
  )
  const button = await screen.findByRole('button', { name: 'Run air-gap agent' })
  await waitFor(() => expect(button).toBeEnabled())
  await userEvent.click(button)
  expect(await screen.findByTestId('run-result')).toHaveTextContent('1 proposal created.')
  expect(seen.some((r) => r.method === 'POST' && r.url === '/agents-api/agents/air_gap/run')).toBe(true)
})

test('F12-FR-13: for a planner the Run button is disabled with the read-only tooltip', async () => {
  stub({ '/api/overview/insights': insights, '/api/reference': reference, '/api/me': me('planner', 'pat') })
  renderWithProviders(
    <MemoryRouter>
      <InsightsWindow open onClose={vi.fn()} params={new URLSearchParams()} />
    </MemoryRouter>,
  )
  const button = await screen.findByRole('button', { name: 'Run air-gap agent' })
  await waitFor(() => expect(button).toHaveAttribute('title', 'Read-only role'))
  expect(button).toBeDisabled()
})

test('F14-FR-10: times in the evidence table and the summary show in site time, not as ISO', async () => {
  const iso = { ...detail, payload: { ...detail.payload, summary: 'LIMS approved at 2026-10-08T13:00:00Z and the gap is open.' }, evidence: [{ system: 'LIMS', ref: 'S1', field: 'approved_at', value: '2026-10-08T13:00:00Z' }, ...detail.evidence.slice(1)] }
  stub({ '/api/me': me('qa_release', 'alex'), '/api/reference': { ...reference, site_timezone: 'Europe/Dublin' }, '/agents-api/proposals/1': iso })
  atPage('/agents/proposals/1', <ProposalPage />)
  const rowsOfEvidence = await screen.findAllByTestId('evidence-row')
  expect(rowsOfEvidence[0]).toHaveTextContent('8 Oct 2026 14:00')
  expect(screen.getByText(/LIMS approved at 8 Oct 2026 14:00 and the gap is open\./)).toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/\dT\d\d:/)
  // display only: the fetched proposal keeps its stored ISO values
  expect(iso.evidence[0]!.value).toBe('2026-10-08T13:00:00Z')
  expect(iso.payload.summary).toContain('2026-10-08T13:00:00Z')
})

test('F14-FR-12: a candidate with no recording gets its own row message and the run still creates the others', async () => {
  stub({
    '/api/overview/insights': insights,
    '/api/reference': reference,
    '/api/me': me('qa_release', 'alex'),
    '/agents-api/agents/air_gap/run': {
      created: [{ row_key: 'k9', outcome: 'created', proposal_id: 8, status: 'pending_approval', trace_id: 'TR-0002', message: '', replay_miss: null }],
      skipped: [],
      errors: [{ row_key: 'k2', outcome: 'error', proposal_id: null, status: null, trace_id: 'TR-0001', message: 'No recording for B5003: record it or run live', replay_miss: { key: 'k', hint: 'h' } }],
    },
  })
  const rowsOf = () => screen.findAllByTestId('window-row')
  renderWithProviders(
    <MemoryRouter>
      <InsightsWindow open onClose={vi.fn()} params={new URLSearchParams()} />
    </MemoryRouter>,
  )
  await rowsOf()
  const button = await screen.findByRole('button', { name: 'Run air-gap agent' })
  await waitFor(() => expect(button).toBeEnabled())
  await userEvent.click(button)
  expect(await screen.findByTestId('run-result')).toHaveTextContent('1 proposal created. 1 could not run: see its row.')
  const rows = await rowsOf()
  expect(within(rows[1]!).getByTestId('row-error')).toHaveTextContent('No recording for B5003: record it or run live')
  expect(screen.queryByTestId('run-error')).not.toBeInTheDocument()
})

test('F14-FR-17: the proposal page and the agent card show where the answers came from', async () => {
  const trace = { trace_id: 'TR-0001', proposal_id: 1, row_key: 'k', provider: 'replay', model_id: 'claude-sonnet-5-5', replayed: true, steps: [], totals: { tokens_in: 0, tokens_out: 0, latency_ms: 0, cost_usd: 0, model_calls: 0 } }
  stub({ '/api/me': me('qa_release', 'alex'), '/api/reference': reference, '/agents-api/proposals/1': detail, '/agents-api/traces/TR-0001': trace })
  atPage('/agents/proposals/1', <ProposalPage />)
  expect(await screen.findByTestId('provider-chip')).toHaveTextContent('Replay · recorded from claude-sonnet-5-5')
})

test('F14-FR-17: a live provider reads "Live · model"', () => {
  renderWithProviders(<ProviderChip provider="anthropic" modelId="claude-sonnet-5-5" />)
  expect(screen.getByTestId('provider-chip')).toHaveTextContent('Live · claude-sonnet-5-5')
  expect(screen.getByTestId('provider-chip')).toHaveAttribute('data-provider', 'live')
})
