import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { describeExplanation, toPlainText, type Explanation } from './ExplainContent'
import { ExplainPopover } from './ExplainPopover'

afterEach(() => vi.unstubAllGlobals())

const freshness = { contract_run_id: 'run-1', last_success_at: '2026-10-12T07:00:00Z', freshness_minutes: 0 }

const stage = {
  kind: 'stage',
  row_key: 'RM1|B1042|1',
  stage_key: 'qc_testing',
  stage_label: 'QC Testing',
  rule: { id: 'R-QCT', stage_key: 'qc_testing', condition_sql: 'x', description: 'Sample collected and not yet approved', inputs: ['lims_status'] },
  input_values: { lims_status: 'in_progress', sample_collected_date: '2026-09-02' },
  source_refs: { lims: { sample: 'S-0000444' } },
  freshness,
} as unknown as Explanation

const metric = {
  kind: 'metric',
  metric_id: 'M3',
  label: 'Sampling On-Time',
  status: 'active',
  null_reason: null,
  week_start: '2026-10-05',
  completed: 2,
  on_time: 1,
  pct: '50.0',
  sla_days: 7,
  rows: [
    { row_key: 'a|1|1', entry_date: '2026-09-28', exit_date: '2026-10-02', duration_days: 4, sla_days: 7, on_time: true },
    { row_key: 'b|2|1', entry_date: '2026-09-20', exit_date: '2026-10-02', duration_days: 12, sla_days: 7, on_time: false },
  ],
  freshness,
} as unknown as Explanation

test('F11-FR-04: a stage explanation gives the rule in words, its inputs, the run id and copyable text', () => {
  const content = describeExplanation(stage)
  expect(content.words).toBe('Rule R-QCT: Sample collected and not yet approved')
  expect(content.sections[0].pairs).toContainEqual(['Sample collected date', '2 Sep 2026'])
  const text = toPlainText(content)
  expect(text).toContain('Pipeline run run-1')
  expect(text).toContain('Lims status: in_progress')
})

test('F11-AC-04: a metric explanation lists as many contributing lots as the week completed', () => {
  const content = describeExplanation(metric)
  expect(content.rows?.data).toHaveLength(2)
  expect(content.sections[0].pairs).toContainEqual(['Completed', '2'])
})

test('F11-FR-04: the popover loads on open, shows the content and copies it', async () => {
  const writeText = vi.fn(async () => undefined)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(metric)))
  vi.stubGlobal('fetch', fetchMock)
  renderWithProviders(<ExplainPopover what="M3" path="/explain" params={new URLSearchParams({ field: 'metric:M3' })} />)
  expect(fetchMock).not.toHaveBeenCalled() // nothing is fetched until it opens
  await userEvent.click(screen.getByRole('button', { name: 'Explain M3' }))
  expect(await screen.findByTestId('explain-body')).toHaveTextContent('M3 · Sampling On-Time')
  expect(screen.getAllByRole('row')).toHaveLength(3) // header + two lots
  await userEvent.click(screen.getByRole('button', { name: 'Copy' }))
  await waitFor(() => expect(writeText).toHaveBeenCalled())
  expect((writeText.mock.calls[0] as unknown as string[])[0]).toContain('Lot\tEntered')
})
