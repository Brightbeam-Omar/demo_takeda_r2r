import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

afterEach(() => vi.unstubAllGlobals())

test('F10-FR-01: the shell routes to the Overview and lists the sidebar pages', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.startsWith('/api/me')
        ? new Response(JSON.stringify({ user_key: 'pat', display_name: 'Pat', role: 'planner' }))
        : new Response('not found', { status: 404 }),
    ),
  )
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
  for (const label of ['Agents', 'Sync Status', 'Audit Log']) {
    expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
  }
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
  expect(screen.getByText('Tier 2')).toBeInTheDocument()
})
