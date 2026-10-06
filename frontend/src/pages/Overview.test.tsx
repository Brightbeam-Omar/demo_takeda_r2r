import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from '../App'

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
  row_key: `RM${n}|B${n}|1`, material_no: `RM${n}`, material_desc: 'x', batch_no: `B${n}`, inspection_lot_no: '1', supplier_batch: null, material_class: null, campaign: null, storage_location: null, stage_key: 'sampling', stage_label: 'Sampling', days_in_stage: 1, adjusted_need_by_date: null, system_need_by_locked: null, next_inspection_date: null, inbound_light: 'grey', deviation_light: 'grey',
  flags: {}, plan: { expected_completion: '2026-10-20', must_complete_by: {}, rag, days_remaining: 3, late: false }, latest_status: null, status_log_count: 0, sample_count: 0,
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

test('F10-FR-09 / F18-FR-05: rows keep the server (exceptions-first) order; the search runs in the browser and is not sent to the API', async () => {
  const seen: { url: string; user: string | null }[] = []
  sessionStorage.setItem('r2r.persona', 'sam')
  window.history.pushState({}, '', '/overview?flag=late&q=RM1')
  stubApi({ freshness, flow_strip: [], on_hold_count: 0, total: 2, mode: 'snapshot', alerts: [], rows: [rowOf(9, 'red'), rowOf(1, 'green')] }, { freshness, filtered: false, week_starts: [], metrics: [] }, seen)
  render(<App />)
  const rows = await screen.findAllByTestId('batch-row')
  expect(rows).toHaveLength(1) // RM1 only: the search narrowed the two server rows
  expect(rows[0]).toHaveAttribute('data-row-key', 'RM1|B1|1')
  const overview = seen.filter((call) => call.url.startsWith('/api/overview'))
  expect(overview.length).toBeGreaterThan(0)
  expect(overview.every((call) => call.user === 'sam' && !call.url.includes('q='))).toBe(true)
  await userEvent.click(screen.getAllByRole('button', { name: 'Clear search' })[0]!)
  expect(await screen.findAllByTestId('batch-row')).toHaveLength(2)
  expect(screen.getAllByTestId('batch-row')[0]).toHaveAttribute('data-row-key', 'RM9|B9|1')
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

test('F17-FR-09 / AC-05: the F10 alert-chip band is gone; late, rejected and on-hold are reached through the tag row', async () => {
  const alerts = [
    { kind: 'late', count: 4, rows: [], detail: {} },
    { kind: 'rejected', count: 2, rows: [], detail: { ud_rejected: 1, lims_rejected: 1 } },
    { kind: 'on_hold', count: 3, rows: [], detail: {} },
    { kind: 'air_gap', count: 1, rows: [], detail: {} },
  ]
  stubApi(
    { freshness, flow_strip: [], on_hold_count: 3, adjusted_count: 0, total: 1, batch_count: 1, mode: 'snapshot', alerts, bookmarks: [], rows: [rowOf(1, 'green')] },
    { freshness, filtered: false, week_starts: [], metrics: [] },
  )
  render(<App />)
  expect(await screen.findByTestId('tag-row')).toBeInTheDocument()
  expect(screen.queryByTestId('alert-late')).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Alerts' })).not.toBeInTheDocument()
  expect(screen.getByTestId('showing-line')).toHaveTextContent('Showing: All in-flight batches')
})

test('F18-FR-07: Export Sampling Plan and Export QC Testing Queue fetch with the persona header and the Overview filters', async () => {
  const seen: { url: string; user: string | null }[] = []
  sessionStorage.setItem('r2r.persona', 'sam')
  window.history.pushState({}, '', '/overview?campaign=CMP-ALPHA&stage=qc_testing&q=RM')
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    seen.push({ url, user: (init?.headers as Record<string, string> | undefined)?.['X-Demo-User'] ?? null })
    if (url.startsWith('/api/export/')) return new Response('material_no\n')
    if (url.startsWith('/api/overview')) return new Response(JSON.stringify({ freshness, flow_strip: [], on_hold_count: 0, total: 1, mode: 'snapshot', alerts: [], rows: [rowOf(1, 'green')] }))
    if (url.startsWith('/api/metrics')) return new Response(JSON.stringify({ freshness, filtered: false, week_starts: [], metrics: [] }))
    return new Response('nf', { status: 404 })
  }))
  render(<App />)
  await screen.findAllByTestId('batch-row')
  await userEvent.click(screen.getAllByRole('button', { name: '↓ Export Sampling Plan' })[0]!)
  await waitFor(() => expect(seen.some((call) => call.url.startsWith('/api/export/sampling-plan.csv'))).toBe(true))
  const plan = seen.find((call) => call.url.startsWith('/api/export/sampling-plan.csv'))!
  expect(plan.user).toBe('sam')
  expect(plan.url).toContain('campaign%5B%5D=CMP-ALPHA')
  expect(plan.url).not.toContain('stage=')
  expect(plan.url).not.toContain('q=')
  await userEvent.click(screen.getAllByRole('button', { name: '↓ Export QC Testing Queue' })[0]!)
  await waitFor(() => expect(seen.some((call) => call.url.startsWith('/api/export/qc-queue.csv'))).toBe(true))
  sessionStorage.clear()
})


const USERS = [
  { user_key: 'pat', display_name: 'Pat', role: 'planner' },
  { user_key: 'sam', display_name: 'Sam', role: 'viewer' },
]

function stubDrawerApp(seen: { url: string; user: string | null }[]) {
  const detail = {
    ...rowOf(7, 'green'),
    inspection_lot_no: '1',
    lot_type: '01',
    ud_date: null,
    plan: { expected_completion: '2026-10-20', must_complete_by: {}, rag: 'green', days_remaining: 3, late: false, compressed: false, compression_ratio: null, effective_slas: {} },
    flags: { released: false, offsite: false },
    siblings: [],
    deviations: [],
    changes: [],
    samples: [],
    status_log: [],
    inbound_check: null,
    current_overrides: {},
    facts: { applicable_sla_json: [], cycle_start_date: null },
  }
  const overview = { freshness, flow_strip: [], on_hold_count: 0, adjusted_count: 0, total: 2, mode: 'snapshot', bookmarks: [], alerts: [], rows: [rowOf(7, 'green'), rowOf(8, 'green')] }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const user = (init?.headers as Record<string, string> | undefined)?.['X-Demo-User'] ?? null
      seen.push({ url, user })
      if (url.startsWith('/api/users')) return new Response(JSON.stringify(USERS))
      if (url.startsWith('/api/metrics')) return new Response(JSON.stringify({ freshness, filtered: false, week_starts: [], metrics: [] }))
      if (url.startsWith('/api/me')) return new Response(JSON.stringify(USERS.find((u) => u.user_key === (user ?? 'pat'))))
      if (url.startsWith('/api/overview')) return new Response(JSON.stringify(overview))
      if (url.startsWith('/api/reference')) return new Response(JSON.stringify({ site_name: 's', site_timezone: 'UTC', stages: [{ stage_key: 'sampling', label: 'Sampling', team: 'QC Lab' }], campaigns: [], molecule_types: [], classes: [], terms: {}, metrics: [], flags: [], periods: [], reason_codes: [], status_options: [], status_reasons: [], metric_rag: { green_min_pct: 90, amber_min_pct: 80 }, air_gap_threshold_hours: 24, release_badge: 'ALPHA – LOCAL' }))
      if (url.startsWith('/api/clock')) return new Response(JSON.stringify({ now_utc: '2026-10-12T07:00:00Z', today_local: '2026-10-12', frozen: false }))
      if (url.startsWith('/api/rows/')) {
        const key = decodeURIComponent(url.slice('/api/rows/'.length))
        return new Response(JSON.stringify({ ...detail, row_key: key, batch_no: key.split('|')[1] }))
      }
      return new Response('nf', { status: 404 })
    }),
  )
}

test('F19-AC-01 / OQ-116: the drawer is non-modal: another row swaps it, the persona switcher works, and closing fills the Batch filter', async () => {
  sessionStorage.clear()
  const seen: { url: string; user: string | null }[] = []
  window.history.pushState({}, '', '/overview?row=' + encodeURIComponent('RM7|B7|1'))
  stubDrawerApp(seen)
  render(<App />)
  const drawer = await screen.findByTestId('batch-drawer')
  expect(await within(drawer).findByText(/Batch B7/)).toBeInTheDocument()

  // The table is still interactive: a click on another row swaps the drawer's content (no close in between).
  await userEvent.click((await screen.findAllByTestId('batch-row'))[1]!)
  expect(await within(screen.getByTestId('batch-drawer')).findByText(/Batch B8/)).toBeInTheDocument()
  expect(window.location.search).toContain('row=RM8%7CB8%7C1')

  // The persona switcher works while the drawer is open (no "close the drawer first").
  await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Persona' }), 'sam')
  await waitFor(() => expect(screen.getByTestId('user-chip')).toHaveTextContent('Sam · Viewer'))
  expect(screen.getByTestId('batch-drawer')).toBeInTheDocument()

  // Closing puts the batch number into the table's Batch filter box.
  await userEvent.click(within(screen.getByTestId('batch-drawer')).getByRole('button', { name: 'Close drawer' }))
  await waitFor(() => expect(screen.queryByTestId('batch-drawer')).not.toBeInTheDocument())
  expect(window.location.search).not.toContain('row=')
  expect(screen.getByLabelText('Filter Batch')).toHaveValue('B8')
  sessionStorage.clear()
})

test('F19-FR-01: ?win=quality&row= opens the Quality window alone and Escape closes it, leaving the table', async () => {
  sessionStorage.clear()
  window.history.pushState({}, '', '/overview?win=quality&row=' + encodeURIComponent('RM7|B7|1'))
  stubDrawerApp([])
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Quality — B7' })).toBeInTheDocument()
  expect(screen.queryByTestId('batch-drawer')).not.toBeInTheDocument() // a window deep link is the window alone
  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Quality — B7' })).not.toBeInTheDocument())
  expect(window.location.search).toBe('')
})

test('F19-FR-01: a window opened from the drawer leaves the drawer open when it closes', async () => {
  sessionStorage.clear()
  window.history.pushState({}, '', '/overview?row=' + encodeURIComponent('RM7|B7|1'))
  stubDrawerApp([])
  render(<App />)
  const drawer = await screen.findByTestId('batch-drawer')
  await userEvent.click(await within(drawer).findByRole('button', { name: 'Open Inbound window' }))
  expect(await screen.findByRole('heading', { name: 'Inbound — B7' })).toBeInTheDocument()
  expect(window.location.search).toContain('win=inbound')
  expect(window.location.search).toContain('drawer=open')
  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Inbound — B7' })).not.toBeInTheDocument())
  expect(screen.getByTestId('batch-drawer')).toBeInTheDocument()
  expect(window.location.search).toBe('?row=RM7%7CB7%7C1')
})
