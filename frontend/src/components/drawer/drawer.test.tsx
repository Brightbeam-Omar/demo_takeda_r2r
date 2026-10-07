import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import type { RowDetail } from '../../api/queries'
import { renderWithProviders } from '../../test-utils'
import { BatchDrawer } from './BatchDrawer'
import { InboundSummary, NeedBySummary, QualitySummary, SamplesSummary, StatusLogSummary } from './Sections'
import { HistorySummary, MilestoneDates, OtherLots, StageTimeline } from './Timeline'

afterEach(() => vi.unstubAllGlobals())

const lot = (n: number, type: string, stage = 'released') =>
  ({ row_key: `RM1|B4410|${n}`, lot_type: type, inspection_lot_no: String(n), stage_key: stage }) as never

const SLAS = [
  { stage_key: 'receipt', sla_days: 10 },
  { stage_key: 'sampling', sla_days: 5 },
  { stage_key: 'qc_testing', sla_days: 27 },
  { stage_key: 'qa_release', sla_days: 3 },
]

function detailOf(extra: Record<string, unknown> = {}, facts: Record<string, unknown> = {}): RowDetail {
  return {
    row_key: 'RM1|B4410|795',
    material_no: 'RM1',
    material_desc: 'Excipient 021',
    batch_no: 'B4410',
    inspection_lot_no: '795',
    lot_type: '09',
    stage_key: 'sampling',
    stage_label: 'Sampling',
    ud_date: null,
    next_inspection_date: '2027-03-01',
    flags: { released: false, offsite: false },
    plan: { effective_slas: { sampling: 5 }, must_complete_by: {} },
    siblings: [],
    deviations: [],
    changes: [],
    samples: [],
    status_log: [],
    status_log_count: 0,
    latest_status: null,
    inbound_check: null,
    current_overrides: {},
    facts: { applicable_sla_json: SLAS, cycle_start_date: '2026-10-08', received_location_type: 'onsite', ...facts },
    ...extra,
  } as unknown as RowDetail
}

test('F19-AC-01: B4410 lists five lots, oldest first, the current one marked and not a link; another lot opens its own drawer', async () => {
  const detail = detailOf({ siblings: [lot(430, '09'), lot(22, '01'), lot(195, '09'), lot(105, '09')] })
  const open = vi.fn()
  render(<OtherLots detail={detail} stageLabel={(k) => k} onOpen={open} />)
  const items = screen.getAllByTestId('lot-item')
  expect(items).toHaveLength(5)
  expect(items.map((item) => item.textContent)).toEqual([
    expect.stringContaining('Initial'),
    expect.stringContaining('Re-eval 1'),
    expect.stringContaining('Re-eval 2'),
    expect.stringContaining('Re-eval 3'),
    expect.stringContaining('Re-eval 4'),
  ])
  expect(items[4]).toHaveTextContent('(current)')
  expect(within(items[4]!).getByRole('button')).toBeDisabled()
  await userEvent.click(within(items[0]!).getByRole('button'))
  expect(open).toHaveBeenCalledWith('RM1|B4410|22')
})

test('F19-AC-01: the summary shows total days against the target in green, or red when over, with the next inspection', () => {
  const summary = (today: string) => (
    <HistorySummary detail={detailOf()} today={today} stageChip={<span>Sampling</span>} tags={<span>RE-EVAL</span>} />
  )
  const { unmount } = render(summary('2026-10-12'))
  expect(screen.getByTestId('total-days')).toHaveTextContent('4d / 45d target')
  expect(screen.getByTestId('total-days').firstElementChild).toHaveAttribute('data-over', 'false')
  expect(screen.getByTestId('history-summary')).toHaveTextContent('1 Mar 2027')
  expect(screen.getByText('RE-EVAL')).toBeInTheDocument()
  unmount()
  render(summary('2026-12-30'))
  expect(screen.getByTestId('total-days').firstElementChild).toHaveAttribute('data-over', 'true')
})

test('F19-FR-01: the stage timeline has a blue current stage, a red stage over its SLA with +Nd over, and 0d for a same-day stage', () => {
  const detail = detailOf(
    { stage_key: 'qc_testing' },
    {
      receipt_entry: '2026-10-01',
      receipt_exit: '2026-10-14',
      sampling_entry: '2026-10-14',
      sampling_exit: '2026-10-14',
      qc_testing_entry: '2026-10-14',
      qc_testing_exit: null,
    },
  )
  render(<StageTimeline detail={detail} today="2026-10-20" stageLabel={(k) => k} />)
  const rows = within(screen.getByTestId('stage-timeline')).getAllByRole('listitem')
  expect(rows.map((row) => row.getAttribute('data-tone'))).toEqual(['red', 'green', 'blue'])
  expect(rows[0]).toHaveTextContent('+3d over')
  expect(rows[0]).toHaveTextContent('13d')
  expect(rows[1]).toHaveTextContent('0d')
  expect(rows[2]).toHaveTextContent('In progress')
  expect(screen.getByText(/stage entered and left on the same day shows 0d/)).toBeInTheDocument()
})

test('F19-FR-01: milestones show their gap, (pending) for missing dates and a dash where they do not apply', () => {
  render(<MilestoneDates detail={detailOf({}, { gr_date: '2026-01-05', sampling_exit: '2026-10-12' })} />)
  const milestones = screen.getByTestId('milestones')
  expect(within(milestones).getByText('Goods Receipt').nextElementSibling).toHaveTextContent('5 Jan 2026')
  expect(within(milestones).getByText('First Sampled').nextElementSibling).toHaveTextContent('+280d from Goods Receipt')
  expect(within(milestones).getByText('Usage Decision').nextElementSibling).toHaveTextContent('(pending)')
  expect(within(milestones).getByText('Call-Off Target').nextElementSibling).toHaveTextContent('—')
})

test('F19-FR-07: the quality summary shows the rating, open deviations and changes (B3150 red, 1 open)', () => {
  const detail = detailOf({
    deviation_light: 'red',
    deviations: [{ deviation_no: 'DEV-000123', severity: 'major', status: 'open' }],
    changes: [{ cc_no: 'CC-1' }, { cc_no: 'CC-2' }],
  })
  render(<QualitySummary detail={detail} />)
  expect(screen.getByRole('img', { name: 'Deviations: red' })).toBeInTheDocument()
  expect(screen.getByTestId('quality-summary')).toHaveTextContent('Red1 open deviation2 changes')
})

test('F19-FR-07: the inbound, status log, samples and need-by summaries show the latest facts', () => {
  const detail = detailOf({
    inbound_check: { prueflos: '1', status: 'failed', deadline: '2026-10-18', failed_count: 2, items: [] },
    latest_status: { status: 'at_risk', label: 'At Risk', colour: 'amber', team: 'QC Lab', comment: 'Waiting for a free analyst', author_user_key: 'quinn' },
    status_log_count: 2,
    samples: [{ sample_id: 'S-1', status: 'rejected' }, { sample_id: 'S-2', status: 'approved' }],
    system_need_by_locked: '2026-12-03',
    adjusted_need_by_date: '2026-11-26',
    adjusted_reason_code: 'CAMPAIGN_PULLED_FORWARD',
    current_overrides: { adjusted_need_by_date: { author_user_key: 'pat' } },
    plan: { expected_completion: '2026-10-14', rag: 'amber', days_remaining: 2, compressed: true, compression_ratio: '0.875', effective_slas: { sampling: 6, qc_testing: 37, qa_release: 6 }, must_complete_by: {} },
  })
  const { container } = renderWithProviders(
    <>
      <InboundSummary detail={detail} />
      <StatusLogSummary detail={detail} />
      <SamplesSummary detail={detail} />
      <NeedBySummary detail={detail} />
    </>,
  )
  expect(screen.getByTestId('inbound-summary')).toHaveTextContent('FailedFailed checks: 2')
  expect(screen.getByTestId('status-summary')).toHaveTextContent('At Risk· QC LabquinnWaiting for a free analyst2 entries in the log')
  expect(screen.getByTestId('samples-summary')).toHaveTextContent('2 samples: 0 received · 1 approved · 1 rejected')
  const needBy = screen.getByTestId('needby-summary')
  expect(needBy).toHaveTextContent('3 Dec 2026')
  expect(needBy).toHaveTextContent('26 Nov 2026')
  expect(needBy).toHaveTextContent('Campaign pulled forward')
  expect(needBy).toHaveTextContent('pat')
  expect(needBy).toHaveTextContent('Compressed to 88% (6 / 37 / 6 d)')
  expect(container).toBeTruthy()
})

function stubDrawerApi(detail: RowDetail) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.startsWith('/api/rows/')) return new Response(JSON.stringify(detail))
      if (url.startsWith('/api/clock')) return new Response(JSON.stringify({ today_local: '2026-10-12' }))
      if (url.startsWith('/api/reference')) return new Response(JSON.stringify({ stages: [{ stage_key: 'sampling', label: 'Sampling' }], terms: {} }))
      return new Response('nf', { status: 404 })
    }),
  )
}

test('F19-FR-07 / OQ-116: the drawer is a non-modal panel whose history sections come first and whose Open ↗ links open the windows', async () => {
  stubDrawerApi(detailOf({ siblings: [lot(22, '01')] }, { gr_date: '2026-01-05' }))
  const onOpenWindow = vi.fn()
  const onClose = vi.fn()
  renderWithProviders(
    <MemoryRouter>
      <button type="button">outside the drawer</button>
      <BatchDrawer rowKey="RM1|B4410|795" onOpenRow={vi.fn()} onClose={onClose} onOpenWindow={onOpenWindow} />
    </MemoryRouter>,
  )
  const drawer = await screen.findByTestId('batch-drawer')
  await within(drawer).findByTestId('stage-timeline')
  const titles = within(drawer)
    .getAllByRole('heading', { level: 3 })
    .map((heading) => heading.textContent)
  expect(titles).toEqual([
    'Batch history', 'Milestone dates', 'Stage timeline', 'Other lots of this batch', 'Quality', 'Inbound', 'Status log', 'Samples', 'Need-by', 'Source refs',
  ])
  expect(drawer).not.toHaveAttribute('aria-modal')
  expect(screen.getByRole('button', { name: 'outside the drawer' })).toBeEnabled() // nothing behind the drawer is made inert

  const links = within(drawer).getAllByRole('button', { name: /^Open .* window$/ })
  expect(links.map((link) => link.getAttribute('data-window'))).toEqual(['quality', 'inbound', 'status', 'samples', 'needby'])
  await userEvent.click(links[0]!)
  expect(onOpenWindow).toHaveBeenCalledWith('quality', 'RM1|B4410|795')

  await userEvent.click(within(drawer).getByRole('button', { name: 'Close drawer' }))
  expect(onClose).toHaveBeenCalledTimes(1)
  await userEvent.keyboard('{Escape}')
  expect(onClose).toHaveBeenCalledTimes(2)
})

test('F12-FR-13: the drawer summary shows the proposal-status line with a link, once a proposal exists', async () => {
  stubDrawerApi(detailOf({ air_gap: true, proposal: { id: 9, status: 'pending_approval', priority: 'high' } }))
  renderWithProviders(
    <MemoryRouter>
      <BatchDrawer rowKey="RM1|B4410|795" onOpenRow={vi.fn()} onClose={vi.fn()} onOpenWindow={vi.fn()} />
    </MemoryRouter>,
  )
  const line = await screen.findByTestId('proposal-line')
  expect(line).toHaveTextContent('Pending approval')
  expect(within(line).getByRole('link', { name: 'View ↗' })).toHaveAttribute('href', '/agents/proposals/9')
  expect(within(screen.getByTestId('batch-drawer')).getByRole('heading', { name: 'Batch history' })).toBeInTheDocument()
})

test('F12-FR-13: a batch that is not an air gap and has no proposal shows no proposal line', async () => {
  stubDrawerApi(detailOf({ air_gap: false, proposal: null }))
  renderWithProviders(
    <MemoryRouter>
      <BatchDrawer rowKey="RM1|B4410|795" onOpenRow={vi.fn()} onClose={vi.fn()} onOpenWindow={vi.fn()} />
    </MemoryRouter>,
  )
  await screen.findByTestId('stage-timeline')
  expect(screen.queryByTestId('proposal-line')).not.toBeInTheDocument()
})
