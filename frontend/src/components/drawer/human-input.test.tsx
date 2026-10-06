import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type { RowDetail } from '../../api/queries'
import { ToastProvider } from '../common/Toasts'
import { Comments } from './Comments'
import { StatusForm } from './StatusForm'

afterEach(() => vi.unstubAllGlobals())

const detail = { row_key: 'RM1|B1|1', latest_status: null, status_log: [] } as unknown as RowDetail

function setup(role: string) {
  const calls: { method: string; url: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ method: init?.method ?? 'GET', url, body: init?.body ? JSON.parse(init.body as string) : null })
      if (url.startsWith('/api/me')) return new Response(JSON.stringify({ user_key: 'u', display_name: 'U', role }))
      if (url.startsWith('/api/reference')) return new Response(JSON.stringify({ stages: [{ team: 'QC Lab' }, { team: 'QA' }, { team: 'QC Lab' }] }))
      return new Response('{}')
    }),
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ToastProvider>
        <StatusForm detail={detail} />
        <Comments detail={detail} />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return calls
}

test('F11-AC-02: as a viewer every edit control is disabled with the read-only tooltip', async () => {
  setup('viewer')
  await waitFor(() => expect(screen.getByLabelText('Status RAG')).toBeDisabled())
  expect(screen.getByLabelText('Status reason')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Set status' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Set status' })).toHaveAttribute('title', 'Read-only role')
  expect(screen.getByLabelText('Add a comment')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Comment' })).toBeDisabled()
})

test('F19-FR-05: a planner may comment and set a status (every role except the viewer)', async () => {
  const calls = setup('planner')
  await waitFor(() => expect(screen.getByLabelText('Add a comment')).toBeEnabled())
  expect(screen.getByLabelText('Status RAG')).toBeEnabled()
  await userEvent.type(screen.getByLabelText('Add a comment'), 'Chased the lab')
  await userEvent.click(screen.getByRole('button', { name: 'Comment' }))
  await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true))
  expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ body: 'Chased the lab' })
})

test('F11-FR-03: a QC lead sets a status with a reason and a team from the stage owners', async () => {
  const calls = setup('qc_lead')
  await waitFor(() => expect(screen.getByLabelText('Status RAG')).toBeEnabled())
  const set = screen.getByRole('button', { name: 'Set status' })
  expect(set).toBeDisabled() // a reason is required
  await userEvent.selectOptions(screen.getByLabelText('Status RAG'), 'amber')
  await userEvent.selectOptions(screen.getByLabelText('Status team'), 'QC Lab')
  expect(screen.getAllByRole('option', { name: 'QC Lab' })).toHaveLength(1) // distinct teams only
  await userEvent.type(screen.getByLabelText('Status reason'), 'Lab backlog')
  await userEvent.click(set)
  await waitFor(() => expect(calls.some((call) => call.method === 'PUT')).toBe(true))
  expect(calls.find((call) => call.method === 'PUT')?.body).toEqual({ rag: 'amber', reason: 'Lab backlog', team: 'QC Lab' })
})
