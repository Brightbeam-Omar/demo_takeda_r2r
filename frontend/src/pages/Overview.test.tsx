import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from '../App'

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

test('F10-FR-10: a failing overview shows an error band with Retry and a loading skeleton first', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.startsWith('/api/overview')
        ? new Response(JSON.stringify({ detail: 'database unavailable' }), { status: 500 })
        : new Response('not found', { status: 404 }),
    ),
  )
  render(<App />)
  expect(screen.getAllByTestId('skeleton').length).toBeGreaterThan(0)
  expect(await screen.findByText(/Could not load the overview: database unavailable/, {}, { timeout: 4000 })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
})
