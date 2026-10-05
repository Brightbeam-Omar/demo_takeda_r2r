import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { ToastProvider } from '../common/Toasts'
import { NeedByModal } from './NeedByModal'

afterEach(() => vi.unstubAllGlobals())

const plan = (expected: string, rag: string, compressed: boolean) => ({
  expected_completion: expected,
  rag,
  compressed,
  compression_ratio: compressed ? '0.61' : null,
  effective_slas: compressed ? { sampling: 6, qc_testing: 37, qa_release: 6 } : { sampling: 7, qc_testing: 42, qa_release: 7 },
})

function setup() {
  const calls: { method: string; url: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(init.body as string) : null
      calls.push({ method: init?.method ?? 'GET', url, body })
      if (url.includes('/need-by/preview'))
        return new Response(JSON.stringify({ current: plan('2026-10-15', 'green', false), preview: body.adjusted_date ? plan('2026-10-14', 'amber', true) : plan('2026-10-15', 'green', false) }))
      if (url.endsWith('/need-by') && init?.method === 'PUT') return new Response('{}')
      if (url.startsWith('/api/rows/'))
        return new Response(JSON.stringify({ row_key: 'RM1|B2077|1', material_no: 'RM1', batch_no: 'B2077', inspection_lot_no: '1', system_need_by_locked: '2026-12-03', adjusted_need_by_date: null, adjusted_reason_code: null, expedite: false }))
      if (url.startsWith('/api/reference'))
        return new Response(JSON.stringify({ stages: [{ stage_key: 'sampling', label: 'Sampling' }, { stage_key: 'qc_testing', label: 'QC Testing' }, { stage_key: 'qa_release', label: 'QA Release' }], reason_codes: [{ code: 'CAMPAIGN_PULLED_FORWARD', label: 'Campaign pulled forward' }] }))
      return new Response('nf', { status: 404 })
    }),
  )
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ToastProvider>
        <NeedByModal rowKey="RM1|B2077|1" onClose={onClose} />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return { calls, onClose }
}

test('F11-FR-02: a date needs a reason, the preview shows the new plan before saving, and Save sends the PUT', async () => {
  const { calls, onClose } = setup()
  await waitFor(() => expect(screen.getByTestId('system-date-box')).toHaveTextContent('3 Dec 2026'))
  await userEvent.type(screen.getByLabelText('Adjusted need-by'), '2026-11-26')
  const save = screen.getByRole('button', { name: 'Save' })
  expect(save).toBeDisabled()
  await userEvent.selectOptions(screen.getByLabelText('Reason'), 'CAMPAIGN_PULLED_FORWARD')
  expect(await screen.findByText(/14 Oct 2026/)).toBeInTheDocument()
  expect(screen.getByTestId('preview-rag')).toHaveTextContent('AMBER')
  expect(screen.getByTestId('preview-compression')).toHaveTextContent('Sampling 6 d / QC Testing 37 d / QA Release 6 d')
  expect(calls.some((call) => call.method === 'PUT')).toBe(false) // previewing writes nothing

  await userEvent.click(save)
  await waitFor(() => expect(onClose).toHaveBeenCalled())
  const put = calls.find((call) => call.method === 'PUT')
  expect(put?.body).toEqual({ adjusted_date: '2026-11-26', reason_code: 'CAMPAIGN_PULLED_FORWARD', expedite: false, note: null })
})
