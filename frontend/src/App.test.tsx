import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

const REFERENCE = {
  site_name: 'Site A',
  site_timezone: 'Europe/Dublin',
  release_badge: 'ALPHA – LOCAL',
  terms: { erp_blocked_tag: 'SAP BLOCKED', lims: 'LIMS' },
}

function stub(role = 'planner', users: unknown = null) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.startsWith('/api/me')) return new Response(JSON.stringify({ user_key: 'pat', display_name: 'Pat', role }))
      if (url.startsWith('/api/reference')) return new Response(JSON.stringify(REFERENCE))
      if (url.startsWith('/api/users') && users) return new Response(JSON.stringify(users))
      return new Response('not found', { status: 404 })
    }),
  )
}

const DEMO_USERS = [{ user_key: 'pat', display_name: 'Pat', role: 'planner' }]

test('F15-FR-02: the sidebar has VIEWS and ADMIN groups with every item, and the release badge', async () => {
  stub()
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'R2R Overview' })).toBeInTheDocument()
  const nav = within(screen.getByRole('navigation', { name: 'Pages' }))
  for (const label of ['Overview', 'Reports & Metrics', 'Agents']) {
    expect(nav.getByRole('link', { name: label })).toBeInTheDocument()
  }
  for (const label of [
    'Team Dashboard',
    'Audit Log',
    'Schema Reference',
    'Upload Data',
    'Process / Campaign Mapping',
    'POC — Integrations',
    'Configuration',
    'SLA Configuration',
    'Sync Status',
    'Webhook Sync Status',
    'Feedback',
  ]) {
    expect(nav.getByRole('link', { name: label })).toBeInTheDocument()
  }
  expect(nav.getByText('VIEWS')).toBeInTheDocument()
  expect(nav.getByText('ADMIN')).toBeInTheDocument()
  expect(await screen.findByTestId('release-badge')).toHaveTextContent('ALPHA – LOCAL')
  expect(screen.getByText('Phase 1: Trusted Data')).toBeInTheDocument()
})

test('F15-FR-02 / OQ-076: ADMIN shows for a non-admin role, and Demo Controls only for admin in DEMO_MODE', async () => {
  stub('planner', DEMO_USERS)
  const { unmount } = render(<App />)
  expect(await screen.findByRole('link', { name: 'Audit Log' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Demo Controls' })).not.toBeInTheDocument()
  unmount()

  stub('admin', DEMO_USERS)
  render(<App />)
  expect(await screen.findByRole('link', { name: 'Demo Controls' })).toBeInTheDocument()
})

test('F15-FR-02: no Demo Controls outside DEMO_MODE, even for admin', async () => {
  stub('admin')
  render(<App />)
  expect(await screen.findByRole('link', { name: 'Audit Log' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Demo Controls' })).not.toBeInTheDocument()
})

test('F20: Reports & Metrics is a built page, not a placeholder', async () => {
  stub()
  render(<App />)
  const nav = within(await screen.findByRole('navigation', { name: 'Pages' }))
  await userEvent.click(nav.getByRole('link', { name: 'Reports & Metrics' }))
  expect(await screen.findByTestId('reports-page')).toBeInTheDocument()
  expect(screen.queryByTestId('placeholder-page')).not.toBeInTheDocument()
})

test.each([
  ['Upload Data', /spreadsheet/, 'T2-07'],
  ['Process / Campaign Mapping', /campaign/, undefined],
  ['POC — Integrations', /source/, 'T2-01'],
  ['Configuration', /site profile/, undefined],
])('F21-FR-06: %s is a placeholder with a paragraph about the capability and a Tier 2 tag', async (label, about, roadmap) => {
  stub()
  render(<App />)
  const nav = within(await screen.findByRole('navigation', { name: 'Pages' }))
  await userEvent.click(nav.getByRole('link', { name: label }))
  const page = await screen.findByTestId('placeholder-page')
  expect(page).toHaveTextContent(label)
  expect(within(page).getByTestId('placeholder-about')).toHaveTextContent(about)
  expect(within(page).getByTestId('tier-tag')).toHaveTextContent(roadmap ? `Tier 2 · ${roadmap}` : 'Tier 2')
})

test('F15-FR-02 / OQ-081: an unbuilt page still renders a titled placeholder', async () => {
  stub()
  render(<App />)
  const nav = within(await screen.findByRole('navigation', { name: 'Pages' }))
  await userEvent.click(nav.getByRole('link', { name: 'Upload Data' }))
  expect(await screen.findByTestId('placeholder-page')).toHaveTextContent('Tier 2')
})

test('F12-FR-12: Agents is a built page, not a placeholder', async () => {
  stub()
  render(<App />)
  const nav = within(await screen.findByRole('navigation', { name: 'Pages' }))
  await userEvent.click(nav.getByRole('link', { name: 'Agents' }))
  expect(await screen.findByTestId('agents-page')).toBeInTheDocument()
  expect(screen.queryByTestId('placeholder-page')).not.toBeInTheDocument()
})

test('F21-FR-06: Team Dashboard, Schema Reference and SLA Configuration are built pages', async () => {
  stub()
  render(<App />)
  const nav = within(await screen.findByRole('navigation', { name: 'Pages' }))
  for (const [label, page] of [
    ['Team Dashboard', 'team-dashboard-page'],
    ['Schema Reference', 'schema-reference-page'],
    ['SLA Configuration', 'sla-config-page'],
    ['Sync Status', 'sync-status-page'],
    ['Webhook Sync Status', 'webhook-status-page'],
  ]) {
    await userEvent.click(nav.getByRole('link', { name: label }))
    expect(await screen.findByTestId(page)).toBeInTheDocument()
    expect(screen.queryByTestId('placeholder-page')).not.toBeInTheDocument()
  }
})

test('F15-FR-02: the sidebar collapses to icons and expands again', async () => {
  stub()
  render(<App />)
  await userEvent.click(await screen.findByRole('button', { name: 'Collapse sidebar' }))
  expect(screen.queryByText('Phase 1: Trusted Data')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Overview' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Expand sidebar' }))
  expect(screen.getByText('Phase 1: Trusted Data')).toBeInTheDocument()
})

test('F15-FR-03: the top bar shows the page title, the period button and the user chip', async () => {
  stub()
  render(<App />)
  expect(await screen.findByTestId('period-button')).toHaveTextContent('All Dates')
  expect(await screen.findByTestId('user-chip')).toHaveTextContent('Pat · Planner')
})

test('F15-FR-07: the persona switcher shows only in DEMO_MODE', async () => {
  stub('planner', DEMO_USERS)
  const { unmount } = render(<App />)
  expect(await screen.findByRole('combobox')).toBeInTheDocument()
  unmount()
  stub('planner')
  render(<App />)
  expect(await screen.findByRole('link', { name: 'Audit Log' })).toBeInTheDocument()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
})
