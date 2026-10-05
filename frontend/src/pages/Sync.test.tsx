import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test-utils'
import { formatDuration, formatRelative } from '../lib/format'
import { Sync } from './Sync'

afterEach(() => vi.unstubAllGlobals())

const status = {
  freshness_minutes: 12,
  pipeline_status: {
    last_run_id: 'abcd1234-0000',
    started_at: '2026-10-12T06:59:00Z',
    last_success_at: '2026-10-12T07:00:00Z',
    row_count: 803,
    source_freshness: { erp: { extracted_at: '2026-10-12T07:00:00Z', max_updated_at: '2026-10-09T12:11:00Z' } },
  },
  watermarks: [{ object_name: 'batch_pipeline_v', run_id: 'abcd1234-0000', synced_at: '2026-10-05T10:00:00Z', age_seconds: 130 }],
  events: [
    { id: 2, source: 'webhook', run_id: 'abcd1234-0000', status: 'pending', received_at: 'x', claimed_at: null, finished_at: null, error: null, rows_upserted: null, age_seconds: 3, duration_ms: null },
    { id: 1, source: 'webhook', run_id: 'eeee5555-0000', status: 'done', received_at: 'x', claimed_at: 'x', finished_at: 'x', error: null, rows_upserted: 1743, age_seconds: 120, duration_ms: 1400 },
  ],
}

function setup(role: string) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? 'GET'} ${url}`)
      if (url.startsWith('/api/sync/status')) return new Response(JSON.stringify(status))
      if (url.startsWith('/api/sync/trigger')) return new Response('{}')
      if (url.startsWith('/api/me')) return new Response(JSON.stringify({ user_key: 'u', display_name: 'U', role }))
      if (url.startsWith('/api/reference')) return new Response(JSON.stringify({ site_timezone: 'Europe/Dublin', stages: [] }))
      return new Response('nf', { status: 404 })
    }),
  )
  renderWithProviders(
    <MemoryRouter>
      <Sync />
    </MemoryRouter>,
  )
  return calls
}

test('F11-FR-05: events show status chips, relative ages and durations, never absolute dates', async () => {
  setup('admin')
  const rows = await screen.findAllByTestId('sync-event')
  expect(rows).toHaveLength(2)
  expect(within(rows[0]).getByTestId('event-status')).toHaveTextContent('pending')
  expect(within(rows[0]).getByText('just now')).toBeInTheDocument()
  expect(within(rows[1]).getByText('2 min ago')).toBeInTheDocument()
  expect(within(rows[1]).getByText('1.4 s')).toBeInTheDocument()
  expect(within(rows[1]).getByRole('link', { name: 'eeee5555' })).toHaveAttribute('href', 'http://localhost:3001/runs/eeee5555-0000')
  expect(screen.getByTestId('last-run')).toHaveTextContent('abcd1234')
  await waitFor(() => expect(screen.getByTestId('pipeline-card')).toHaveTextContent('Mon 12 Oct 2026 08:00'))
  expect(screen.getByTestId('watermarks')).toHaveTextContent('batch_pipeline_v')
  expect(screen.getByTestId('source-freshness')).toHaveTextContent('erp')
})

test('F11-FR-05: Trigger sync works for an admin and is disabled with the tooltip for other roles', async () => {
  const calls = setup('admin')
  const button = await screen.findByRole('button', { name: 'Trigger sync' })
  await waitFor(() => expect(button).toBeEnabled())
  await userEvent.click(button)
  await waitFor(() => expect(calls).toContain('POST /api/sync/trigger'))
})

test('F11-FR-05: a planner sees Trigger sync disabled', async () => {
  setup('planner')
  const button = await screen.findByRole('button', { name: 'Trigger sync' })
  await waitFor(() => expect(button).toBeDisabled())
  expect(button).toHaveAttribute('title', 'Read-only role')
})

test('F11-FR-05: relative ages and durations read naturally', () => {
  expect(formatRelative(4)).toBe('just now')
  expect(formatRelative(75)).toBe('1 min ago')
  expect(formatRelative(7200)).toBe('2 h ago')
  expect(formatDuration(850)).toBe('850 ms')
  expect(formatDuration(65_000)).toBe('1 min 5 s')
})

test('F11-FR-05: an event without a run id has no Dagster link', async () => {
  status.events[0].run_id = null as unknown as string
  setup('admin')
  const rows = await screen.findAllByTestId('sync-event')
  expect(within(rows[0]).queryByRole('link')).not.toBeInTheDocument()
  status.events[0].run_id = 'abcd1234-0000'
})
