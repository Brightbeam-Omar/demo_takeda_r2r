import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { SyncStatus } from './SyncStatus'

afterEach(() => vi.unstubAllGlobals())

const runs = [
  { pipeline_run_id: 'cccc3333-0000', started_at: '2026-10-12T07:00:00Z', age_seconds: 120, duration_ms: 1400, files: 18, inserted: 0, total: 803, skipped: 803, status: 'ok', failed_step: null },
  { pipeline_run_id: 'bbbb2222-0000', started_at: '2026-10-12T06:00:00Z', age_seconds: 3700, duration_ms: 900, files: 18, inserted: null, total: null, skipped: null, status: 'failed', failed_step: 'transform' },
  { pipeline_run_id: 'aaaa1111-0000', started_at: '2026-10-12T05:00:00Z', age_seconds: 7300, duration_ms: 61_000, files: 18, inserted: 803, total: 803, skipped: 0, status: 'ok', failed_step: null },
]
const steps = {
  pipeline_run_id: 'bbbb2222-0000',
  steps: [
    { step: 'setup', status: 'success', started_at: 'x', finished_at: 'x', duration_ms: 80, rows: null, error: null },
    { step: 'transform', status: 'failed', started_at: 'x', finished_at: 'x', duration_ms: 1200, rows: null, error: 'RuntimeError: forced failure' },
  ],
}

function setup() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.startsWith('/api/pipeline/runs/bbbb2222-0000/steps')) return new Response(JSON.stringify(steps))
      if (url.startsWith('/api/pipeline/runs')) return new Response(JSON.stringify(runs))
      return new Response('nf', { status: 404 })
    }),
  )
  renderWithProviders(
    <MemoryRouter>
      <SyncStatus />
    </MemoryRouter>,
  )
}

test('F21-FR-02: the title line, the clock note and one row per run, newest first, with relative ages', async () => {
  setup()
  const rows = await screen.findAllByTestId('run-row')
  expect(screen.getByTestId('page-subtitle')).toHaveTextContent('History of every pipeline run — click a Run ID to see per-step detail')
  expect(screen.getByTestId('clock-note')).toHaveAttribute('title', expect.stringContaining('demo clock'))
  expect(rows).toHaveLength(3)
  expect(within(rows[0]).getByTestId('run-link')).toHaveTextContent('cccc3333')
  expect(rows[0]).toHaveTextContent('2 min ago')
  expect(rows[0]).toHaveTextContent('1.4 s')
  expect(rows[2]).toHaveTextContent('1 min 1 s')
  expect(rows[0]).not.toHaveTextContent(/2026/) // never an absolute date (OQ-054)
})

test('F21-FR-02 / OQ-129: a failed run shows FAILED with its step and dashes for the figures', async () => {
  setup()
  const failed = (await screen.findAllByTestId('run-row'))[1]
  expect(within(failed).getByTestId('run-status')).toHaveTextContent('FAILED')
  expect(within(failed).getByTestId('run-status')).toHaveTextContent('transform')
  expect(failed).toHaveTextContent('—')
  expect(within((await screen.findAllByTestId('run-row'))[0]).getByTestId('run-status')).toHaveTextContent('OK')
})

test('F21-FR-02: a Run ID opens the per-step window with status, duration, rows and the error', async () => {
  setup()
  await userEvent.click(within((await screen.findAllByTestId('run-row'))[1]).getByTestId('run-link'))
  const window = await screen.findByTestId('run-steps-window')
  const stepRows = await within(window).findAllByTestId('run-step')
  expect(stepRows.map((row) => row.querySelector('td')?.textContent)).toEqual(['setup', 'transform'])
  expect(stepRows[1]).toHaveTextContent('failed')
  expect(stepRows[1]).toHaveTextContent('1.2 s')
  expect(stepRows[1]).toHaveTextContent('RuntimeError: forced failure')
})

test('F21-FR-02: each run links to Dagster', async () => {
  setup()
  const links = await screen.findAllByRole('link', { name: /Open run .* in Dagster/ })
  expect(links[0]).toHaveAttribute('href', 'http://localhost:3001/runs/cccc3333-0000')
})
