import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from '../common/Toasts'
import { FeedbackButton } from './FeedbackButton'

afterEach(() => vi.unstubAllGlobals())

test('F15-FR-06: the modal shows the page, needs a message, and posts it', async () => {
  const fetchMock = vi.fn(async () => new Response('{}', { status: 201 }))
  vi.stubGlobal('fetch', fetchMock)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ToastProvider>
        <MemoryRouter initialEntries={['/audit']}>
          <FeedbackButton />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
  await userEvent.click(screen.getByTestId('feedback-button'))
  expect(screen.getByTestId('feedback-page')).toHaveTextContent('/audit')
  expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Feedback message'), 'More filters please')
  await userEvent.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('/api/feedback')
  expect(JSON.parse(String(init.body))).toEqual({
    page: '/audit',
    message: 'More filters please',
  })
  await waitFor(() => expect(screen.queryByTestId('feedback-modal')).not.toBeInTheDocument())
})
