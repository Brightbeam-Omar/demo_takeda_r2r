import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../App'

const USERS = [
  { user_key: 'pat', display_name: 'Pat', role: 'planner' },
  { user_key: 'sam', display_name: 'Sam', role: 'viewer' },
]

const calls: { url: string; user: string | null }[] = []

beforeEach(() => {
  calls.length = 0
  sessionStorage.clear()
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const user = (init?.headers as Record<string, string> | undefined)?.['X-Demo-User'] ?? null
      calls.push({ url, user })
      if (url.startsWith('/api/users')) return new Response(JSON.stringify(USERS))
      if (url.startsWith('/api/me')) return new Response(JSON.stringify(USERS.find((u) => u.user_key === (user ?? 'pat'))))
      return new Response('{}', { status: 404 })
    }),
  )
})
afterEach(() => vi.unstubAllGlobals())

test('F10-FR-02 / F10-AC-02: switching to Sam sends X-Demo-User, persists it and shows "Sam · Viewer"', async () => {
  render(<App />)
  const select = await screen.findByRole('combobox', { name: 'Persona' })
  expect(await screen.findByTestId('user-chip')).toHaveTextContent('Pat · Planner')

  await userEvent.selectOptions(select, 'sam')

  await waitFor(() => expect(screen.getByTestId('user-chip')).toHaveTextContent('Sam · Viewer'))
  expect(sessionStorage.getItem('r2r.persona')).toBe('sam')
  expect(calls.some((call) => call.url.startsWith('/api/me') && call.user === 'sam')).toBe(true)
})
