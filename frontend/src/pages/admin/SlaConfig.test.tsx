import { screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { SlaConfig } from './SlaConfig'

afterEach(() => vi.unstubAllGlobals())

const reference = {
  site_timezone: 'Europe/Dublin',
  profile_file: 'site_a.yaml',
  stages: [
    { stage_key: 'receipt', label: 'Receipt', sla_days: 10, reeval_sla_days: null, team: 'Warehouse', show_card: true, terminal: false },
    { stage_key: 'qc_testing', label: 'QCL Testing', sla_days: 42, reeval_sla_days: 27, team: 'QC Lab', show_card: true, terminal: false },
    { stage_key: 'pending', label: 'Pending', sla_days: 0, reeval_sla_days: null, team: 'Logistics', show_card: false, terminal: false },
    { stage_key: 'released', label: 'Released', sla_days: 0, reeval_sla_days: null, team: 'QA', show_card: true, terminal: true },
  ],
  metrics: [
    { metric_id: 'M3', label: 'Sampling On-Time', stage_key: 'sampling', sla_days: 7, entry_event: 'Transferred to site', exit_event: 'Sample collected', window: 'Weekly (ISO week)', status: 'active' },
    { metric_id: 'M5', label: 'External Test On-Time', stage_key: null, sla_days: 30, entry_event: null, exit_event: null, window: 'Tier 2', status: 'awaiting_signal' },
  ],
}

function setup() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (url.startsWith('/api/reference') ? new Response(JSON.stringify(reference)) : new Response('nf', { status: 404 }))))
  renderWithProviders(
    <MemoryRouter>
      <SlaConfig />
    </MemoryRouter>,
  )
}

test('F21-FR-06: the note names the active profile file and says when a change takes effect', async () => {
  setup()
  const note = await screen.findByTestId('sla-note')
  expect(note).toHaveTextContent('Configured in the site profile site_a.yaml; changes take effect at the next pipeline run.')
})

test('F21-FR-06: stages show label, SLA, re-eval SLA, team and whether the card is shown', async () => {
  setup()
  const rows = await screen.findAllByTestId('sla-stage')
  expect(rows).toHaveLength(4)
  expect(rows[1]).toHaveTextContent('QCL Testing')
  expect(rows[1]).toHaveTextContent('42')
  expect(rows[1]).toHaveTextContent('27')
  expect(rows[1]).toHaveTextContent('QC Lab')
  expect(rows[1]).toHaveTextContent('Yes')
  expect(rows[2]).toHaveTextContent('No') // pending has no card
  expect(within(rows[0]).getAllByRole('cell')[2]).toHaveTextContent('—') // no re-eval override
})

test('F21-FR-06: metrics show entry, exit, SLA and window, with dashes where they do not apply', async () => {
  setup()
  const rows = await screen.findAllByTestId('sla-metric')
  expect(rows[0]).toHaveTextContent('M3 · Sampling On-Time')
  expect(rows[0]).toHaveTextContent('Sample collected')
  expect(rows[0]).toHaveTextContent('Weekly (ISO week)')
  expect(within(rows[1]).getAllByRole('cell')[1]).toHaveTextContent('—')
  expect(rows[1]).toHaveTextContent('Tier 2')
})
