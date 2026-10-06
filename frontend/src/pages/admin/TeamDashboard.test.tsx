import { screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { TeamDashboard } from './TeamDashboard'

afterEach(() => vi.unstubAllGlobals())

const teams = {
  teams: [
    { team: 'Logistics', stage_keys: ['pending'], stage_labels: ['Pending'], open: 0, late: 0, oldest_late_days: null, amber: 0, at_risk_pct: null },
    { team: 'QC Lab', stage_keys: ['qc_ship', 'qc_testing'], stage_labels: ['QCL Ship For External Testing', 'QCL Testing'], open: 12, late: 5, oldest_late_days: 34, amber: 3, at_risk_pct: 25 },
  ],
  totals: { open: 12, late: 5, amber: 3 },
}

function setup() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (url.startsWith('/api/teams') ? new Response(JSON.stringify(teams)) : new Response('nf', { status: 404 }))))
  renderWithProviders(
    <MemoryRouter>
      <TeamDashboard />
    </MemoryRouter>,
  )
}

test('F21-FR-06: each team shows open, late, oldest late and at-risk share', async () => {
  setup()
  const rows = await screen.findAllByTestId('team-row')
  const qc = rows[1]
  expect(within(qc).getByTestId('team-open')).toHaveTextContent('12')
  expect(within(qc).getByTestId('team-late')).toHaveTextContent('5')
  expect(within(qc).getByTestId('team-oldest')).toHaveTextContent('34d over')
  expect(within(qc).getByTestId('team-risk')).toHaveTextContent('3 · 25.0%')
  expect(rows[0]).toHaveTextContent('—')
  expect(screen.getByTestId('team-total-late')).toHaveTextContent('5')
})

test('F21-FR-06: a team row links to the Overview filtered to its stages', async () => {
  setup()
  const link = await screen.findByRole('link', { name: 'View QC Lab in the Overview' })
  expect(link).toHaveAttribute('href', '/overview?stage=qc_ship&stage=qc_testing')
})
