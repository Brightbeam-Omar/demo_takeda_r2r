import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { EMPTY_FILTERS } from '../../state/url-filters'
import { PeriodSelector } from './PeriodSelector'

function setup(onChange = vi.fn()) {
  render(
    <MemoryRouter>
      <PeriodSelector filters={EMPTY_FILTERS} today="2026-10-12" onChange={onChange} />
    </MemoryRouter>,
  )
  return onChange
}

test('F10-FR-05: choosing This week sets the period and clears any custom dates', async () => {
  const onChange = setup()
  await userEvent.click(screen.getByRole('button', { name: 'Period' }))
  await userEvent.click(screen.getByRole('menuitemradio', { name: 'This week' }))
  expect(onChange).toHaveBeenCalledWith({ period: 'this_week', from: null, to: null })
})

test('F10-FR-05: a custom range needs two picked days in the two-month calendar', async () => {
  const onChange = setup()
  await userEvent.click(screen.getByRole('button', { name: 'Period' }))
  await userEvent.click(screen.getByRole('menuitemradio', { name: 'Custom range…' }))
  expect(screen.getByText('October 2026')).toBeInTheDocument()
  expect(screen.getByText('November 2026')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '12 Oct 2026' }))
  await userEvent.click(screen.getByRole('button', { name: '18 Nov 2026' }))
  await userEvent.click(screen.getByRole('button', { name: 'Apply' }))
  expect(onChange).toHaveBeenCalledWith({ period: 'custom', from: '2026-10-12', to: '2026-11-18' })
})
