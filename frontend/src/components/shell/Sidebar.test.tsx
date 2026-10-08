import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { Sidebar } from './Sidebar'

afterEach(() => vi.unstubAllGlobals())

function setup(hide: boolean) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.startsWith('/api/me')) return new Response(JSON.stringify({ user_key: 'admin', display_name: 'Admin', role: 'admin' }))
      if (url === '/api/users') return new Response(JSON.stringify([{ user_key: 'admin', display_name: 'Admin', role: 'admin' }]))
      if (url.startsWith('/api/reference')) {
        return new Response(JSON.stringify({ site_name: 'Site A', site_timezone: 'UTC', terms: {}, stages: [], release_badge: 'X', demo: { default_columns: [], hide_placeholders: hide } }))
      }
      return new Response('nf', { status: 404 })
    }),
  )
  renderWithProviders(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  )
}

const PLACEHOLDERS = ['Upload Data', 'Process / Campaign Mapping', 'POC — Integrations', 'Configuration']

test('F14-FR-16: with hide_placeholders the four Tier 2 placeholder items are not in the menu', async () => {
  setup(true)
  await screen.findByRole('link', { name: 'Demo Controls' })
  await screen.findByText('X')
  for (const label of PLACEHOLDERS) expect(screen.queryByRole('link', { name: label })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Sync Status' })).toBeInTheDocument()
})

test('F14-FR-16: without the flag the placeholders are listed', async () => {
  setup(false)
  await screen.findByRole('link', { name: 'Demo Controls' })
  for (const label of PLACEHOLDERS) expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
})
