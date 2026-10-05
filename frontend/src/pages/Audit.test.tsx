import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { auditLines } from '../components/audit/AuditDetails'
import { renderWithProviders } from '../test-utils'
import { Audit } from './Audit'

afterEach(() => vi.unstubAllGlobals())

const items = [
  { id: 3, at: '2026-10-12T07:05:00Z', actor_user_key: 'pat', action: 'need_by_set', row_key: 'RM1|B2077|1', details: { field: 'adjusted_need_by_date', old: null, new: '2026-11-26', reason_code: 'CAMPAIGN_PULLED_FORWARD', note: 'campaign moved' } },
  { id: 2, at: '2026-10-12T07:04:00Z', actor_user_key: 'sam', action: 'forbidden', row_key: 'RM1|B2077|1', details: { method: 'PUT', path: '/api/rows/x/need-by', required_roles: ['planner', 'admin'], role: 'viewer' } },
]

function setup() {
  const urls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      urls.push(url)
      if (url.startsWith('/api/audit')) return new Response(JSON.stringify({ total: 2, limit: 50, offset: 0, items }))
      if (url.startsWith('/api/users')) return new Response(JSON.stringify([{ user_key: 'pat', display_name: 'Pat', role: 'planner' }]))
      if (url.startsWith('/api/reference')) return new Response(JSON.stringify({ site_timezone: 'Europe/Dublin', stages: [] }))
      return new Response('nf', { status: 404 })
    }),
  )
  renderWithProviders(
    <MemoryRouter>
      <Audit />
    </MemoryRouter>,
  )
  return urls
}

test('F11-FR-06: old → new reads as a sentence, and non-override entries show labelled fields', () => {
  expect(auditLines(items[0].details)).toEqual([
    ['Need-by', 'system date → 26 Nov 2026'],
    ['Reason', 'Campaign pulled forward'],
    ['Note', 'campaign moved'],
  ])
  expect(auditLines(items[1].details)).toContainEqual(['Required roles', 'planner, admin'])
  expect(auditLines({ field: 'manual_status', old: null, new: { rag: 'amber', team: 'QC Lab' } })[0]).toEqual(['Status', 'none → AMBER · QC Lab'])
})

test('F11-FR-06: entries expand to their details and the filters, including the date range, go to the API', async () => {
  const urls = setup()
  const rows = await screen.findAllByTestId('audit-entry')
  expect(rows).toHaveLength(2)
  expect(screen.queryByTestId('audit-details')).not.toBeInTheDocument()
  await userEvent.click(within(rows[0]).getByRole('button', { name: /Show details/ }))
  expect(screen.getByTestId('audit-details')).toHaveTextContent('system date → 26 Nov 2026')

  await userEvent.selectOptions(screen.getByLabelText('Action'), 'forbidden')
  await userEvent.type(screen.getByLabelText('From'), '2026-10-12')
  await waitFor(() => expect(urls.some((url) => url.includes('action=forbidden') && url.includes('from=2026-10-12'))).toBe(true))
})

test('F11-FR-06: a "to" before "from" is flagged and not sent', async () => {
  const urls = setup()
  await screen.findAllByTestId('audit-entry')
  await userEvent.type(screen.getByLabelText('From'), '2026-10-12')
  await userEvent.type(screen.getByLabelText('To'), '2026-10-10')
  expect(await screen.findByRole('alert')).toHaveTextContent('before')
  expect(urls.filter((url) => url.includes('to=2026-10-10'))).toHaveLength(0)
})
