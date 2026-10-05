import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, expect, test, vi } from 'vitest'
import App from '../App'

// jsdom has no layout, so give the scroll container a size for the virtualiser.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 400 })
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 1200 })
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

test('F10-FR-10: a failing overview shows an error band with Retry and a loading skeleton first', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.startsWith('/api/overview')
        ? new Response(JSON.stringify({ detail: 'database unavailable' }), { status: 500 })
        : new Response('not found', { status: 404 }),
    ),
  )
  render(<App />)
  expect(screen.getAllByTestId('skeleton').length).toBeGreaterThan(0)
  expect(await screen.findByText(/Could not load the overview: database unavailable/, {}, { timeout: 4000 })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
})

const freshness = { contract_run_id: 'r1', last_success_at: null, freshness_minutes: 0 }
const rowOf = (n: number, rag: string) => ({
  row_key: `RM${n}|B${n}|1`, material_no: `RM${n}`, material_desc: 'x', batch_no: `B${n}`, stage_key: 'sampling', stage_label: 'Sampling',
  flags: {}, plan: { expected_completion: '2026-10-20', rag, days_remaining: 3 }, manual_status: null,
})

function stubApi(overview: object, metrics: object, seen: { url: string; user: string | null }[] = []) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      seen.push({ url, user: (init?.headers as Record<string, string> | undefined)?.['X-Demo-User'] ?? null })
      if (url.startsWith('/api/overview')) return new Response(JSON.stringify(overview))
      if (url.startsWith('/api/metrics')) {
        return 'detail' in metrics ? new Response(JSON.stringify(metrics), { status: 500 }) : new Response(JSON.stringify(metrics))
      }
      if (url.startsWith('/api/reference')) return new Response(JSON.stringify({ site_name: 's', site_timezone: 'UTC', stages: [], campaigns: [], molecule_types: [], classes: [] }))
      if (url.startsWith('/api/export.csv')) return new Response('row_key\n')
      if (url.startsWith('/api/me')) return new Response(JSON.stringify({ user_key: 'sam', display_name: 'Sam', role: 'viewer' }))
      return new Response('nf', { status: 404 })
    }),
  )
}

test('F10-FR-10: empty states for no batches and no metrics', async () => {
  stubApi({ freshness, flow_strip: [], on_hold_count: 0, total: 0, mode: 'snapshot', alerts: [], rows: [] }, { freshness, filtered: false, week_starts: [], metrics: [] })
  render(<App />)
  expect(await screen.findByText('No batches yet. The pipeline has not published any data.')).toBeInTheDocument()
  expect(await screen.findByText('No metrics are published yet.')).toBeInTheDocument()
})

test('F10-FR-10: a failing metrics call shows its own error band while the table still renders', async () => {
  stubApi({ freshness, flow_strip: [], on_hold_count: 0, total: 1, mode: 'snapshot', alerts: [], rows: [rowOf(1, 'green')] }, { detail: 'boom' })
  render(<App />)
  expect(await screen.findByText(/Could not load the weekly metrics: boom/, {}, { timeout: 4000 })).toBeInTheDocument()
})

test('F10-FR-09: rows keep the server (exceptions-first) order and Export CSV sends the persona header and current filters', async () => {
  const seen: { url: string; user: string | null }[] = []
  sessionStorage.setItem('r2r.persona', 'sam')
  window.history.pushState({}, '', '/overview?flag=late&q=RM')
  stubApi({ freshness, flow_strip: [], on_hold_count: 0, total: 2, mode: 'snapshot', alerts: [], rows: [rowOf(9, 'red'), rowOf(1, 'green')] }, { freshness, filtered: false, week_starts: [], metrics: [] }, seen)
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  render(<App />)
  const rows = await screen.findAllByTestId('batch-row')
  expect(rows[0]).toHaveAttribute('data-row-key', 'RM9|B9|1')
  await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
  await waitFor(() => expect(seen.some((call) => call.url.startsWith('/api/export.csv'))).toBe(true))
  const call = seen.find((entry) => entry.url.startsWith('/api/export.csv'))!
  expect(call.user).toBe('sam')
  expect(call.url).toContain('flags%5B%5D=late')
  expect(call.url).toContain('q=RM')
  sessionStorage.clear()
})

test('F11-FR-07 / OQ-072: an unknown ?row= shows "Batch not found" and Escape removes only the row parameter', async () => {
  window.history.pushState({}, '', '/overview?q=RM&row=' + encodeURIComponent('NOPE|B0|0'))
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.startsWith('/api/rows/')) return new Response(JSON.stringify({ detail: 'unknown row' }), { status: 404 })
    if (url.startsWith('/api/overview')) return new Response(JSON.stringify({ freshness, flow_strip: [], on_hold_count: 0, total: 0, mode: 'snapshot', alerts: [], rows: [] }))
    return new Response('nf', { status: 404 })
  }))
  render(<App />)
  expect(await screen.findByText(/Batch not found: NOPE\|B0\|0/)).toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByText(/Batch not found/)).not.toBeInTheDocument())
  expect(window.location.search).toBe('?q=RM')
})

test('F16-FR-06/08: the banners show the counts and open their windows; zero counts are the blue empty states', async () => {
  const overview = (adjusted: number, gaps: number) => ({
    freshness, flow_strip: [], on_hold_count: 0, adjusted_count: adjusted, total: 0, mode: 'snapshot', bookmarks: [],
    alerts: [{ kind: 'air_gap', count: gaps, rows: [], detail: {} }], rows: [],
  })
  let body = overview(2, 4)
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.startsWith('/api/overview/insights')) {
      return new Response(JSON.stringify({ total: 1, rows: [{ row_key: 'k', batch_no: 'B5003', material_no: 'RM1', material_desc: 'One', stage_key: 'qa_release', stage_label: 'QA Release', air_gap_hours: 25, days_gap: 1 }] }))
    }
    if (url.startsWith('/api/overview/adjusted')) return new Response(JSON.stringify({ total: 0, rows: [] }))
    if (url.startsWith('/api/overview')) return new Response(JSON.stringify(body))
    if (url.startsWith('/api/metrics')) return new Response(JSON.stringify({ freshness, filtered: false, week_starts: [], metrics: [] }))
    return new Response('nf', { status: 404 })
  }))
  const first = render(<App />)
  expect(await screen.findByTestId('adjusted-banner')).toHaveTextContent('2 adjusted needs-by dates')
  expect(screen.getByTestId('insights-banner')).toHaveTextContent('LIMS–ERP Insights (4 batches)')
  await userEvent.click(screen.getByRole('button', { name: 'View all 4 →' }))
  expect(await screen.findByText('B5003')).toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByText('B5003')).not.toBeInTheDocument())
  first.unmount()

  body = overview(0, 0)
  render(<App />)
  expect(await screen.findByText(/No adjusted needs-by dates in this period/)).toBeInTheDocument()
  expect(screen.getByText(/No LIMS–ERP Insights in this period/)).toBeInTheDocument()
})
