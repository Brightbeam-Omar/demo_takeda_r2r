import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { expect, test } from 'vitest'
import type { Reference, Row } from '../../api/queries'
import { useUrlFilters } from '../../state/url-filters'
import { FiltersBand } from './FiltersBand'

const reference = {
  molecule_types: ['small_molecule', 'peptide'],
  classes: ['drug_substance'],
  campaigns: ['CMP-ALPHA', 'CMP-BRAVO'],
} as unknown as Reference
const rows = [{ campaign: 'CMP-ALPHA' }, { campaign: 'CMP-ALPHA' }, { campaign: 'CMP-BRAVO' }] as unknown as Row[]

function Harness() {
  const { filters, update, clearAll } = useUrlFilters()
  const location = useLocation()
  const [, force] = useState(0)
  return (
    <>
      <FiltersBand reference={reference} rows={rows} filters={filters} stageLabel={(k) => k} onChange={(p) => { update(p); force((n) => n + 1) }} onClear={clearAll} />
      <output data-testid="url">{location.search}</output>
    </>
  )
}

test('F10-FR-04: chips, dropdowns and the summary write to the URL and Clear all resets them', async () => {
  render(
    <MemoryRouter initialEntries={['/overview?stage=qc_testing']}>
      <Harness />
    </MemoryRouter>,
  )
  expect(screen.getByTestId('active-filters')).toHaveTextContent('1 filter active · Stage: qc_testing')

  await userEvent.click(screen.getByRole('button', { name: 'HOLD' }))
  await userEvent.click(screen.getByRole('button', { name: 'REJECTED' }))
  expect(screen.getByTestId('url')).toHaveTextContent(/flag=on_hold&flag=ud_rejected&flag=lims_rejected&stage=qc_testing/)

  await userEvent.click(screen.getByRole('button', { name: /Campaign/ }))
  expect(screen.getByText('CMP-ALPHA').parentElement).toHaveTextContent('2')
  await userEvent.click(screen.getByRole('checkbox', { name: /CMP-BRAVO/ }))
  expect(screen.getByTestId('url')).toHaveTextContent('campaign=CMP-BRAVO')

  await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
  expect(screen.getByTestId('url')).toHaveTextContent('')
  expect(screen.queryByTestId('active-filters')).not.toBeInTheDocument()
})
