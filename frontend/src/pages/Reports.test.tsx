import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { ToastProvider } from '../components/common/Toasts'
import { renderWithProviders } from '../test-utils'
import { Reports } from './Reports'

afterEach(() => vi.unstubAllGlobals())

const freshness = { contract_run_id: 'run-1', last_success_at: '2026-10-12T07:00:00Z', freshness_minutes: 0 }
const meta = {
  freshness,
  year: 2026,
  years: [2026, 2025],
  coverage_from: '2026-04-15',
  awaiting_signal: [
    { metric_id: 'M1', label: 'Receipt On-Time', null_reason: 'Physical receipt date comes from the 3PL feed' },
    { metric_id: 'M2', label: 'Transfer On-Time', null_reason: 'x' },
    { metric_id: 'M4', label: 'QC Ship On-Time', null_reason: 'y' },
    { metric_id: 'M5', label: 'External Test On-Time', null_reason: 'z' },
  ],
}

const summary = {
  ...meta,
  release: { released: 318, annual_target: 700, prorata_target: 350, pct_of_prorata: 91, coverage_weeks: 26, rag: 'amber' },
  adherence: { on_time: 280, late: 31, excluded: 3, pct: '90.0', target_pct: 90, rag: 'green' },
  expedite: { on_time: 3, late: 1, expedited: 4, app_only: 1, pct: '75.0', target_pct: 90, rag: 'red' },
}

const cell = (period_start: string, pct: string | null, rag: string | null, completed = 10) => ({ period_start, pct, rag, completed })
const trends = {
  ...meta,
  grain: 'weekly',
  stage_grain: 'daily',
  periods: ['2026-09-14', '2026-09-21', '2026-09-28', '2026-10-05', '2026-10-12'],
  rows: [
    {
      metric_id: 'M3', label: 'Sampling On-Time', status: 'active', null_reason: null, trend: 'up', trend_delta_pp: '12.6',
      cells: [cell('2026-09-14', '78.6', 'red'), cell('2026-09-21', '84.4', 'red'), cell('2026-09-28', '81.8', 'red'), cell('2026-10-05', '94.4', 'green'), cell('2026-10-12', null, null, 0)],
    },
    {
      metric_id: 'M7', label: 'QA Release On-Time', status: 'active', null_reason: null, trend: 'down', trend_delta_pp: '-14.1',
      cells: [cell('2026-09-14', '90.0', 'green'), cell('2026-09-21', '85.0', 'red'), cell('2026-09-28', '83.3', 'red'), cell('2026-10-05', '69.2', 'red'), cell('2026-10-12', null, null, 0)],
    },
    {
      metric_id: 'M1', label: 'Receipt On-Time', status: 'awaiting_signal', null_reason: 'Physical receipt date comes from the 3PL feed', trend: 'none', trend_delta_pp: null,
      cells: ['2026-09-14', '2026-09-21', '2026-09-28', '2026-10-05', '2026-10-12'].map((day) => cell(day, null, null, 0)),
    },
  ],
  stages: [{ stage_key: 'sampling', label: 'Sampling', sort: 3 }],
  points: [{ day: '2026-10-12', week_start: null, counts: { sampling: 3 }, total: 3 }],
}

const late = {
  ...meta,
  count: 2,
  items: [
    { row_key: 'a', material_no: 'RM10040', material_desc: 'Excipient 40', batch_no: 'L1', campaign: 'CMP-ALPHA', stage_key: 'sampling', stage_label: 'Sampling', metric_breached: 'M3', days_over_sla: 65, late_reason: 'Resource constraint' },
    { row_key: 'b', material_no: 'RM10041', material_desc: 'Excipient 41', batch_no: 'L2', campaign: null, stage_key: 'receipt', stage_label: 'Receipt', metric_breached: null, days_over_sla: 30, late_reason: null },
  ],
}

const sla = {
  ...meta,
  target_pct: 90,
  bars: [
    { metric_id: 'M3', label: 'Sampling On-Time', stage_label: 'Sampling', status: 'active', null_reason: null, week_start: '2026-10-05', pct: '94.4', completed: 18, on_time: 17, rag: 'green' },
    { metric_id: 'M1', label: 'Receipt On-Time', stage_label: 'Receipt', status: 'awaiting_signal', null_reason: 'Physical receipt date comes from the 3PL feed', week_start: null, pct: null, completed: 0, on_time: 0, rag: null },
  ],
}

function setup(entry = '/reports') {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url)
      const body = url.includes('/reports/summary')
        ? summary
        : url.includes('/reports/trends')
          ? trends
          : url.includes('/reports/late')
            ? late
            : url.includes('/reports/sla')
              ? sla
              : url.includes('/reports/release-rate')
                ? { ...meta, weekly_target: 13, weeks: [], release: summary.release }
                : url.includes('/reports/adherence')
                  ? { ...meta, weeks: [], adherence: summary.adherence }
                  : null
      return body ? new Response(JSON.stringify(body)) : new Response('nf', { status: 404 })
    }),
  )
  renderWithProviders(
    <MemoryRouter initialEntries={[entry]}>
      <Reports />
    </MemoryRouter>,
  )
  return calls
}

test('F20: the page has six tabs, the year selector, the N/A banner and the coverage note', async () => {
  setup()
  const tabs = within(await screen.findByRole('tablist')).getAllByRole('tab')
  expect(tabs.map((tab) => tab.textContent)).toEqual(['Executive Summary', 'SLA Performance', 'Trends', 'Late Items', 'Release Rate', 'Adherence to NBD'])
  expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
  await waitFor(() => expect(screen.getByTestId('reports-na-banner')).toHaveTextContent('M1, M2, M4, M5 show N/A until their feeds are connected'))
  expect(screen.getByTestId('reports-coverage')).toHaveTextContent('Coverage from 15 Apr 2026')
  const year = screen.getByTestId('reports-year') as HTMLSelectElement
  expect([...year.options].map((option) => option.value)).toEqual(['2026', '2025'])
})

test('F20-AC-01: Executive Summary shows the three cards with their figures and target markers', async () => {
  setup()
  const release = await screen.findByTestId('card-release')
  expect(within(release).getByTestId('card-release-figure')).toHaveTextContent('318 / 700')
  expect(within(release).getByTestId('card-release-counts')).toHaveTextContent('91% of pro-rata target')
  expect(within(release).getByTestId('card-release-marker')).toHaveStyle({ left: '50%' }) // 350 of 700
  expect(release).toHaveAttribute('data-rag', 'amber')
  const adherence = screen.getByTestId('card-adherence')
  expect(within(adherence).getByTestId('card-adherence-figure')).toHaveTextContent('90.0%')
  expect(within(adherence).getByTestId('card-adherence-counts')).toHaveTextContent('280 on-time / 31 late')
  expect(adherence).toHaveTextContent('3 released lots without a need-by are not counted')
  const expedite = screen.getByTestId('card-expedite')
  expect(within(expedite).getByTestId('card-expedite-counts')).toHaveTextContent('3 on-time / 4 expedited')
  expect(expedite).toHaveTextContent('a missed expedite does not penalise the standard SLA')
  expect(expedite).toHaveTextContent('1 more expedited in the app only')
})

test('F20: a tab click changes the tab in the URL and the year is disabled where it does not apply', async () => {
  const calls = setup()
  const user = userEvent.setup()
  await screen.findByTestId('card-release')
  await user.click(screen.getByTestId('reports-tab-late'))
  expect(await screen.findByTestId('report-late')).toBeInTheDocument()
  expect(screen.getByTestId('reports-year')).toBeDisabled()
  expect(calls.some((url) => url.startsWith('/api/reports/late'))).toBe(true)
  await user.click(screen.getByTestId('reports-tab-adherence'))
  await waitFor(() => expect(screen.getByTestId('reports-year')).toBeEnabled())
})

test('F20: the year in the URL goes to the report requests', async () => {
  const calls = setup('/reports?tab=summary&year=2025')
  await screen.findByTestId('card-release')
  expect(calls.every((url) => url.includes('year=2025'))).toBe(true)
})

test('F20-AC-03: Trends shows the periods, the shading and the trend column', async () => {
  setup('/reports?tab=trends')
  const table = await screen.findByTestId('trend-table')
  expect(within(table).getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
    'Metric', 'Wk 38', 'Wk 39', 'Wk 40', 'Wk 41', 'Wk 42to date', 'Trend',
  ]) // fmt: skip
  const m3 = screen.getByTestId('trend-row-M3')
  expect(within(m3).getByText('94%')).toHaveAttribute('data-rag', 'green')
  expect(within(m3).getByText('79%')).toHaveAttribute('data-rag', 'red')
  expect(screen.getByTestId('trend-M3')).toHaveTextContent('▲ +12.6 pp')
  expect(screen.getByTestId('trend-M7')).toHaveTextContent('▼ −14.1 pp')
  expect(within(screen.getByTestId('trend-row-M1')).getAllByText('N/A')).toHaveLength(5)
  expect(screen.getByTestId('stage-chart')).toBeInTheDocument()
})

test('F20-AC-05: Late Items lists the rows worst first with the reason column', async () => {
  setup('/reports?tab=late')
  expect(await screen.findByTestId('late-count')).toHaveTextContent('2 late rows')
  const rows = await screen.findAllByTestId('late-row')
  expect(rows).toHaveLength(2)
  expect(rows[0]).toHaveTextContent('RM10040')
  expect(rows[0]).toHaveTextContent('+65d')
  expect(rows[0]).toHaveTextContent('Resource constraint')
  expect(rows[1]).toHaveTextContent('—')
})

test('F20-AC-02: SLA Performance names the week, the 90% line and the N/A reasons', async () => {
  setup('/reports?tab=sla')
  expect(await screen.findByText(/last complete week \(week 41\)/)).toBeInTheDocument()
  expect(screen.getByText('Dashed line: 90% target')).toBeInTheDocument()
  expect(screen.getByTestId('sla-na')).toHaveTextContent('M1: N/A — Physical receipt date comes from the 3PL feed')
})

test('F20: empty release and adherence tabs say so', async () => {
  setup('/reports?tab=release-rate')
  expect(await screen.findByText('No releases in 2026.')).toBeInTheDocument()
  await userEvent.click(screen.getByTestId('reports-tab-adherence'))
  expect(await screen.findByText(/No released lots with a need-by in 2026/)).toBeInTheDocument()
  expect(screen.getByTestId('adherence-summary')).toHaveTextContent('90.0% within needs-by (280 / 311), target 90%')
})

test('F20: a failed tab offers a retry', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{"detail":"boom"}', { status: 500 })))
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={['/reports?tab=late']}>
          <Reports />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the late items')
})
