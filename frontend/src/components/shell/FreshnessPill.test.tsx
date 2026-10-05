import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { DemoClock } from './DemoClock'
import { FreshnessPill } from './FreshnessPill'

afterEach(() => vi.unstubAllGlobals())

function stub(nowUtc: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.startsWith('/api/clock')) return new Response(JSON.stringify({ now_utc: nowUtc, today_local: '2026-10-12', frozen: false }))
      if (url.startsWith('/api/sync/status'))
        return new Response(JSON.stringify({ events: [], watermarks: [], freshness_minutes: 0, pipeline_status: { last_success_at: '2026-10-12T07:00:00Z' } }))
      return new Response(JSON.stringify({ site_name: 'Site A', site_timezone: 'Europe/Dublin' }))
    }),
  )
}

function renderBoth() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FreshnessPill />
      <DemoClock />
    </QueryClientProvider>,
  )
}

test('F10-FR-03: the pill is green with the age in demo time, and the clock shows site-local time', async () => {
  stub('2026-10-12T07:12:00Z')
  renderBoth()
  expect(await screen.findByText(/Data current · last pipeline run 12 min ago/)).toBeInTheDocument()
  expect(await screen.findByTestId('demo-clock')).toHaveTextContent('Mon 12 Oct 2026 08:12')
})

test('F10-FR-03: the pill turns red beyond 12 demo hours', async () => {
  stub('2026-10-12T20:00:00Z')
  renderBoth()
  expect(await screen.findByText(/Data stale · last pipeline run 13 h ago/)).toBeInTheDocument()
})
