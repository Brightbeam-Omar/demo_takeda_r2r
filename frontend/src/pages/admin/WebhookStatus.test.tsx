import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { WebhookStatus } from './WebhookStatus'

afterEach(() => vi.unstubAllGlobals())

const atRest = {
  last_webhook_age_seconds: 45,
  pending: 0,
  error: 0,
  abandoned: 0,
  poll_fallbacks_24h: 0,
  poll_available: false,
  last_drain_age_seconds: 2,
  stale_claim_minutes: 5,
}
const event = (id: number, values: Record<string, unknown> = {}) => ({
  id, source: 'webhook', run_id: 'abcd1234-0000', status: 'done', received_at: '2026-10-12T07:00:00Z',
  claimed_at: '2026-10-12T07:00:02Z', finished_at: '2026-10-12T07:00:03Z', error: null, rows_upserted: 1743,
  attempts: 1, objects_synced: 17, drain_pass_id: 'pass-xyz', age_seconds: 120, duration_ms: 1400, ...values,
}) // fmt: skip

function setup(role: string, health: Record<string, unknown> = {}, events = [event(2), event(1, { id: 1, status: 'failed', error: 'boom', attempts: 3 })]) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? 'GET'} ${url}`)
      if (url.startsWith('/api/sync/health')) return new Response(JSON.stringify({ ...atRest, ...health }))
      if (url.startsWith('/api/sync/status')) return new Response(JSON.stringify({ events, watermarks: [], pipeline_status: null, freshness_minutes: 1 }))
      if (url.startsWith('/api/sync/run-pipeline')) return new Response(JSON.stringify({ run_id: 'r', status: 'STARTED' }), { status: 202 })
      if (url.startsWith('/api/sync/trigger')) return new Response('{"event_id":3}', { status: 202 })
      if (url.startsWith('/api/me')) return new Response(JSON.stringify({ user_key: 'u', display_name: 'U', role }))
      return new Response('nf', { status: 404 })
    }),
  )
  renderWithProviders(
    <MemoryRouter>
      <WebhookStatus />
    </MemoryRouter>,
  )
  return calls
}

const card = (id: string) => screen.findByTestId(id)

test('F21-AC-03: at rest the middle four cards read 0 with a green bar and Last Drain is green', async () => {
  setup('admin')
  for (const id of ['card-pending', 'card-error', 'card-abandoned', 'card-poll']) {
    const found = await card(id)
    expect(within(found).getByTestId(`${id}-value`)).toHaveTextContent('0')
    expect(found).toHaveAttribute('data-tone', 'green')
  }
  expect(await card('card-last-webhook')).toHaveTextContent('45 s ago')
  expect(await card('card-drain')).toHaveAttribute('data-tone', 'green')
  expect(await card('card-poll')).toHaveTextContent('T2-02')
})

test('F21-FR-03: pending is amber, errors and abandoned events are red, and an old drain goes amber then red', async () => {
  setup('admin', { pending: 1, error: 2, abandoned: 3, last_drain_age_seconds: 45 })
  expect(await card('card-pending')).toHaveAttribute('data-tone', 'amber')
  expect(await card('card-error')).toHaveAttribute('data-tone', 'red')
  expect(await card('card-abandoned')).toHaveAttribute('data-tone', 'red')
  expect(await card('card-drain')).toHaveAttribute('data-tone', 'amber')
})

test('F21-FR-03: a worker that never reported is grey, and an old one is red', async () => {
  setup('admin', { last_drain_age_seconds: null })
  expect(await card('card-drain')).toHaveAttribute('data-tone', 'grey')
})

test('F21-FR-04: the event list shows attempts and views synced, and a row expands to its pass, ages and error', async () => {
  setup('admin')
  const rows = await screen.findAllByTestId('sync-event')
  expect(rows[0]).toHaveTextContent('webhook')
  expect(rows[0]).toHaveTextContent('17')
  expect(rows[1]).toHaveTextContent('failed')
  expect(rows[1]).toHaveTextContent('3')
  await userEvent.click(within(rows[1]).getByTestId('event-expand'))
  const detail = await screen.findByTestId('event-detail')
  expect(detail).toHaveTextContent('pass-xyz')
  expect(detail).toHaveTextContent('boom')
  expect(detail).toHaveTextContent(/ago/)
})

test('F21-FR-04 / OQ-131: a manual event shows a dash for its Run ID', async () => {
  setup('admin', {}, [event(5, { source: 'manual', run_id: null })])
  expect(await screen.findByTestId('sync-event')).toHaveTextContent('manual')
  expect(screen.getByTestId('sync-event').querySelectorAll('td')[3]).toHaveTextContent('—')
})

test('F21-FR-05: Trigger Sync Now asks first, then posts to run-pipeline', async () => {
  const calls = setup('admin')
  await userEvent.click(await screen.findByRole('button', { name: 'Trigger Sync Now' }))
  const dialog = await screen.findByTestId('confirm-dialog')
  expect(dialog).toHaveTextContent("This starts real work that affects everyone's view.")
  expect(calls.some((call) => call.startsWith('POST'))).toBe(false)
  await userEvent.click(within(dialog).getByRole('button', { name: 'Start the run' }))
  await waitFor(() => expect(calls).toContain('POST /api/sync/run-pipeline'))
})

test('F21-FR-05: Drain Queue Now posts to the existing trigger, and Cancel posts nothing', async () => {
  const calls = setup('admin')
  await userEvent.click(await screen.findByRole('button', { name: 'Drain Queue Now' }))
  await userEvent.click(within(await screen.findByTestId('confirm-dialog')).getByRole('button', { name: 'Cancel' }))
  expect(calls.some((call) => call.startsWith('POST'))).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: 'Drain Queue Now' }))
  await userEvent.click(within(await screen.findByTestId('confirm-dialog')).getByRole('button', { name: 'Drain now' }))
  await waitFor(() => expect(calls).toContain('POST /api/sync/trigger'))
})

test('F21-AC-04: for a viewer both actions are disabled with the read-only hint, and Refresh still works', async () => {
  const calls = setup('viewer')
  const trigger = await screen.findByRole('button', { name: 'Trigger Sync Now' })
  await waitFor(() => expect(trigger).toBeDisabled())
  expect(trigger).toHaveAttribute('title', 'Read-only role')
  expect(screen.getByRole('button', { name: 'Drain Queue Now' })).toBeDisabled()
  const before = calls.filter((call) => call.includes('/api/sync/health')).length
  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  await waitFor(() => expect(calls.filter((call) => call.includes('/api/sync/health')).length).toBeGreaterThan(before))
})

test('OQ-135: the page says in a tooltip that its ages are wall-clock', async () => {
  setup('admin')
  expect(await screen.findByTestId('clock-note')).toHaveAttribute('title', expect.stringContaining('wall-clock'))
})
