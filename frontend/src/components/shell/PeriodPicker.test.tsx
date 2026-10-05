import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { PeriodPicker } from './PeriodPicker'

const ALL = { period: 'all', from: null, to: null }

function setup(onChange = vi.fn(), filters = ALL) {
  render(<PeriodPicker filters={filters} today="2026-10-12" onChange={onChange} />)
  return onChange
}

test('F15-FR-04: Quick Select lists the seven options and applies one at once', async () => {
  const onChange = setup()
  await userEvent.click(screen.getByRole('button', { name: 'Period' }))
  for (const label of ['This Week', 'Last Week', 'Next Week', 'This Month', 'Last Month', 'Next Month', 'All Dates']) {
    expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
  }
  await userEvent.click(screen.getByRole('button', { name: 'Last Month' }))
  expect(onChange).toHaveBeenCalledWith({
    period: 'last_month',
    from: null,
    to: null,
  })
})

test('F15-FR-04: the active option is highlighted and the trigger shows its label', async () => {
  setup(vi.fn(), { period: 'last_month', from: null, to: null })
  expect(screen.getByRole('button', { name: 'Period' })).toHaveTextContent('Last Month')
  await userEvent.click(screen.getByRole('button', { name: 'Period' }))
  expect(screen.getByRole('button', { name: 'Last Month', pressed: true })).toBeInTheDocument()
})

test('F15-AC-02: a custom range needs two clicks before Apply is enabled, with the hint changing', async () => {
  const onChange = setup()
  await userEvent.click(screen.getByRole('button', { name: 'Period' }))
  expect(screen.getByText('October 2026')).toBeInTheDocument()
  expect(screen.getByText('November 2026')).toBeInTheDocument()
  expect(screen.getByTestId('period-hint')).toHaveTextContent('Click a date to start')
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '12 Oct 2026' }))
  expect(screen.getByTestId('period-hint')).toHaveTextContent('Click an end date')
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '18 Nov 2026' }))
  await userEvent.click(screen.getByRole('button', { name: 'Apply' }))
  expect(onChange).toHaveBeenCalledWith({
    period: 'custom',
    from: '2026-10-12',
    to: '2026-11-18',
  })
})

test('F15-FR-04: the trigger shows a custom range as dates', () => {
  setup(vi.fn(), { period: 'custom', from: '2026-10-12', to: '2026-11-18' })
  expect(screen.getByRole('button', { name: 'Period' })).toHaveTextContent('12 Oct 2026 – 18 Nov 2026')
})
