import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { parseFrames } from '../../api/demo'
import { renderWithProviders } from '../../test-utils'
import { DemoControls } from './DemoControls'

afterEach(() => vi.unstubAllGlobals())

const step = (id: string, values: Record<string, unknown> = {}) => ({
  id, title: `Title of ${id}`, talk_track: `Say this about ${id}`, group: 'Extras', preconditions: 'met', messages: [], actions: ['one'], ...values,
}) // fmt: skip

const frame = (seq: number, kind: string, message: string) => `id: ${seq}\ndata: ${JSON.stringify({ seq, kind, message, elapsed_ms: seq * 1500 })}\n\n`

function stream(text: string): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text))
      controller.close()
    },
  })
  return new Response(body, { headers: { 'content-type': 'text/event-stream' } })
}

interface Options {
  role?: string
  steps?: unknown[]
  runs?: Record<string, { status: number; body: unknown }>
  events?: string
}

function setup({ role = 'admin', steps = [step('lims-approve-B1042'), step('ud-post-B5003', { preconditions: 'unmet', messages: ['B5003 is no longer an air gap.'] })], runs = {}, events }: Options = {}) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? 'GET'} ${url}`)
      if (url.startsWith('/api/me')) return new Response(JSON.stringify({ user_key: 'u', display_name: 'U', role }))
      if (url === '/api/demo/steps') return new Response(JSON.stringify(steps))
      const run = Object.entries(runs).find(([path]) => url === `/api/demo/${path}`)
      if (run) return new Response(JSON.stringify(run[1].body), { status: run[1].status })
      if (url.includes('/events')) return stream(events ?? frame(0, 'start', 'Started') + frame(1, 'done', 'Finished'))
      return new Response('nf', { status: 404 })
    }),
  )
  renderWithProviders(
    <MemoryRouter>
      <DemoControls />
    </MemoryRouter>,
  )
  return calls
}

test('F13-FR-06: every step shows its title, talk track and a Run button', async () => {
  setup()
  const rows = await screen.findAllByTestId('demo-step')
  expect(rows).toHaveLength(2)
  expect(within(rows[0]!).getByText('Title of lims-approve-B1042')).toBeInTheDocument()
  expect(within(rows[0]!).getByText('Say this about lims-approve-B1042')).toBeInTheDocument()
  expect(within(rows[0]!).getByRole('button', { name: 'Run Title of lims-approve-B1042' })).toBeEnabled()
})

test('F13-FR-06: the precondition light shows ready or not available, with the reason', async () => {
  setup()
  const lights = await screen.findAllByTestId('precondition-light')
  expect(lights.map((light) => light.getAttribute('data-state'))).toEqual(['met', 'unmet'])
  expect(screen.getByText('B5003 is no longer an air gap.')).toBeInTheDocument()
})

test('F13-AC-04: running a step shows its progress lines as they arrive and ends with the status', async () => {
  const calls = setup({ runs: { 'steps/lims-approve-B1042/run': { status: 202, body: { run_id: 'abc' } } } })
  await userEvent.click(await screen.findByRole('button', { name: 'Run Title of lims-approve-B1042' }))
  const lines = await screen.findAllByTestId('progress-line')
  expect(lines.map((line) => line.textContent)).toEqual(['0.0 sStarted', '1.5 sFinished'])
  await waitFor(() => expect(screen.getByTestId('run-status')).toHaveAttribute('data-status', 'succeeded'))
  expect(calls).toContain('POST /api/demo/steps/lims-approve-B1042/run')
  expect(calls).toContain('GET /api/demo/runs/abc/events?after=0')
})

test('F13-AC-04: a failed run shows the failure line in red and the status failed', async () => {
  setup({
    runs: { 'steps/lims-approve-B1042/run': { status: 202, body: { run_id: 'abc' } } },
    events: frame(0, 'start', 'Started') + frame(1, 'failed', 'lims POST /events/approved answered 409'),
  })
  await userEvent.click(await screen.findByRole('button', { name: 'Run Title of lims-approve-B1042' }))
  await waitFor(() => expect(screen.getByTestId('run-status')).toHaveAttribute('data-status', 'failed'))
  expect((await screen.findAllByTestId('progress-line')).at(-1)).toHaveAttribute('data-kind', 'failed')
})

test('F13-AC-02: a refused step shows the server message and no progress (the list was stale: it said met)', async () => {
  setup({
    steps: [step('ud-post-B5003')],
    runs: { 'steps/ud-post-B5003/run': { status: 409, body: { detail: { error: 'precondition_failed', message: 'B5003 is no longer an air gap.' } } } },
  })
  await userEvent.click(await screen.findByRole('button', { name: 'Run Title of ud-post-B5003' }))
  expect(await screen.findByTestId('step-refused')).toHaveTextContent('B5003 is no longer an air gap.')
  expect(screen.queryAllByTestId('progress-line')).toHaveLength(0)
})

test('F13-FR-06: Reset demo asks first and Cancel starts nothing', async () => {
  const calls = setup()
  await userEvent.click(await screen.findByRole('button', { name: 'Reset demo' }))
  const dialog = await screen.findByTestId('confirm-dialog')
  expect(dialog).toHaveTextContent('clears bookmarks')
  await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
  expect(calls.some((call) => call.includes('/reset'))).toBe(false)
})

test('F13-FR-06: confirming Reset demo starts the reset and follows it', async () => {
  const calls = setup({ runs: { reset: { status: 202, body: { run_id: 'r1' } } } })
  await userEvent.click(await screen.findByRole('button', { name: 'Reset demo' }))
  await userEvent.click(within(await screen.findByTestId('confirm-dialog')).getByRole('button', { name: 'Reset demo' }))
  await waitFor(() => expect(calls).toContain('POST /api/demo/reset'))
  await waitFor(() => expect(screen.getByTestId('run-status')).toHaveAttribute('data-status', 'succeeded'))
})

test('F13-AC-04: while a run is going every Run button and Reset are disabled', async () => {
  setup({
    runs: { 'steps/lims-approve-B1042/run': { status: 202, body: { run_id: 'abc' } } },
    events: frame(0, 'start', 'Started'), // the stream ends without "done": the page keeps the run open
  })
  await userEvent.click(await screen.findByRole('button', { name: 'Run Title of lims-approve-B1042' }))
  await waitFor(() => expect(screen.getByTestId('run-status')).toHaveAttribute('data-status', 'running'))
  expect(screen.getByRole('button', { name: 'Run Title of ud-post-B5003' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Reset demo' })).toBeDisabled()
})

test('F13-AC-04: for anyone but an admin the page says so and loads no steps', async () => {
  const calls = setup({ role: 'planner' })
  expect(await screen.findByTestId('demo-forbidden')).toHaveTextContent('for admins')
  expect(calls).not.toContain('GET /api/demo/steps')
})

test('F13-FR-03: the stream parser keeps an unfinished frame for the next chunk', () => {
  const text = frame(0, 'start', 'a') + 'id: 1\ndata: {"seq": 1, "ki'
  const first = parseFrames(text)
  expect(first.events.map((event) => event.message)).toEqual(['a'])
  const second = parseFrames(first.rest + 'nd": "line", "message": "b", "elapsed_ms": 1}\n\n')
  expect(second.events.map((event) => event.message)).toEqual(['b'])
})

test('F14-FR-09: Run is disabled for an unmet step with the reason as its tooltip; unknown and met stay enabled', async () => {
  setup({
    steps: [
      step('lims-approve-B1042'),
      step('ud-post-B5003', { preconditions: 'unmet', messages: ['B5003 is no longer an air gap.'] }),
      step('run-pipeline', { preconditions: 'unknown', messages: ['Could not check.'] }),
    ],
  })
  const rows = await screen.findAllByTestId('demo-step')
  const run = (index: number) => within(rows[index]!).getByRole('button', { name: /^Run / })
  expect(run(0)).toBeEnabled()
  expect(run(1)).toBeDisabled()
  expect(within(rows[1]!).getByTestId('run-reason')).toHaveAttribute('title', 'B5003 is no longer an air gap.')
  expect(run(2)).toBeEnabled()
})

test('F14-FR-13: the steps sit under their act headings, in the order the scenario lists them', async () => {
  setup({
    steps: [
      step('lims-approve-B1042', { group: 'Act 3' }),
      step('pull-forward-B2077', { group: 'Act 5' }),
      step('airgap-agent', { group: 'Act 6' }),
      step('ud-post-B5003', { group: 'After act 6' }),
      step('advance-day'),
    ],
  })
  const groups = await screen.findAllByTestId('demo-group')
  expect(groups.map((group) => group.getAttribute('data-group'))).toEqual(['Act 3', 'Act 5', 'Act 6', 'After act 6', 'Extras'])
  expect(within(groups[3]!).getByText('Title of ud-post-B5003')).toBeInTheDocument()
  expect(within(groups[3]!).getByRole('heading', { name: 'After act 6' })).toBeInTheDocument()
})
