import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Overview } from '../../api/queries'
import { AlertsBand } from './AlertsBand'

type Alerts = Overview['alerts']

const alerts = [
  { kind: 'air_gap', count: 2, rows: [{ batch_no: 'B1428', air_gap_hours: 408 }], detail: {} },
  { kind: 'late', count: 0, rows: [], detail: {} },
  { kind: 'rejected', count: 11, rows: [], detail: { ud_rejected: 6, lims_rejected: 5 } },
] as unknown as Alerts

test('F10-FR-06: zero-count alerts are hidden, air gap lists its top items, and a click filters to the flags', async () => {
  const onFilter = vi.fn()
  render(<AlertsBand alerts={alerts} onFilter={onFilter} />)
  expect(screen.queryByTestId('alert-late')).not.toBeInTheDocument()
  expect(screen.getByTestId('alert-air_gap')).toHaveTextContent('B1428 (408 h)')
  expect(screen.getByTestId('alert-rejected')).toHaveTextContent('6 usage decision · 5 LIMS')
  await userEvent.click(screen.getByTestId('alert-rejected'))
  expect(onFilter).toHaveBeenCalledWith({ flags: ['ud_rejected', 'lims_rejected'] })
})

test('F10-FR-06: the whole band is hidden when every count is zero', () => {
  const zero = (alerts as unknown as { kind: string }[]).map((alert) => ({ ...alert, count: 0 })) as unknown as Alerts
  const { container } = render(<AlertsBand alerts={zero} onFilter={vi.fn()} />)
  expect(container).toBeEmptyDOMElement()
})
