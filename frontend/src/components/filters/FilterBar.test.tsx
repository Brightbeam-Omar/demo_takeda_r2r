import { act, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Reference, Row } from '../../api/queries'
import { useUrlFilters } from '../../state/url-filters'
import { renderWithProviders } from '../../test-utils'
import { FilterBar } from './FilterBar'

const reference = {
  molecule_types: [
    { key: 'small_molecule', label: 'Small Molecule' },
    { key: 'large_molecule', label: 'Large Molecule' },
    { key: 'peptide', label: 'Peptides' },
  ],
  classes: [
    { key: 'consumable', label: 'Consumable' },
    { key: 'drug_substance', label: 'Drug Substance' },
  ],
  campaigns: ['CMP-ALPHA', 'CMP-BRAVO', 'CMP-CHARLIE'],
} as unknown as Reference
const rows = [
  { campaign: 'CMP-ALPHA', material_class: 'consumable' },
  { campaign: 'CMP-ALPHA', material_class: null },
  { campaign: 'CMP-BRAVO', material_class: null },
] as unknown as Row[]

function Harness({ bookmarks = [] }: { bookmarks?: string[] }) {
  const { filters, update, clearAll } = useUrlFilters()
  const location = useLocation()
  return (
    <>
      <FilterBar reference={reference} rows={rows} filters={filters} stageLabel={(k) => k} bookmarks={bookmarks} onChange={update} onClear={clearAll} />
      <output data-testid="url">{location.search}</output>
    </>
  )
}

const renderAt = (entry = '/overview', bookmarks: string[] = []) =>
  renderWithProviders(
    <MemoryRouter initialEntries={[entry]}>
      <Harness bookmarks={bookmarks} />
    </MemoryRouter>,
  )

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('[]'))) // the presets menu loads the (empty) list
})

afterEach(() => {
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

test('F16-FR-01: the Filters button toggles the panel and the state is in the URL', async () => {
  renderAt()
  expect(screen.queryByRole('group', { name: 'Type' })).not.toBeInTheDocument()
  const toggle = screen.getByRole('button', { name: /Filters/ })
  expect(toggle).toHaveTextContent('▾')
  await userEvent.click(toggle)
  expect(screen.getByRole('group', { name: 'Type' })).toBeInTheDocument()
  expect(toggle).toHaveTextContent('▴')
  expect(screen.getByTestId('url')).toHaveTextContent('filters=open')
  await userEvent.click(toggle)
  expect(screen.getByTestId('url')).toHaveTextContent('filters=closed')
})

test('F16-FR-01: ?filters=open opens the panel on load', () => {
  renderAt('/overview?filters=open')
  expect(screen.getByRole('group', { name: 'Class' })).toBeInTheDocument()
})

test('F16-AC-01: selections collapse to chips, and removing a chip updates the URL', async () => {
  renderAt()
  await userEvent.click(screen.getByRole('button', { name: /Filters/ }))
  await userEvent.click(within(screen.getByRole('group', { name: 'Type' })).getByRole('button', { name: 'Small Molecule' }))
  const classes = within(screen.getByRole('group', { name: 'Class' }))
  await userEvent.click(classes.getByRole('button', { name: 'Consumable' }))
  await userEvent.click(classes.getByRole('button', { name: 'Drug Substance' }))
  await userEvent.click(screen.getByRole('button', { name: /Filters/ }))

  const chips = screen.getByTestId('filter-chips')
  expect(within(chips).getByText('Type: Small Molecule')).toBeInTheDocument()
  expect(within(chips).getByText('Class: 2 classes')).toBeInTheDocument()
  expect(screen.getByTestId('url')).toHaveTextContent(/type=small_molecule&class=consumable&class=drug_substance/)

  await userEvent.click(screen.getByRole('button', { name: 'Remove Class: 2 classes' }))
  expect(screen.getByTestId('url')).not.toHaveTextContent('class=')
  expect(screen.getByTestId('url')).toHaveTextContent('type=small_molecule')
  expect(screen.queryByText('Class: 2 classes')).not.toBeInTheDocument()
})

test('F16-FR-03: Clear all removes every chip', async () => {
  renderAt('/overview?type=peptide&campaign=CMP-ALPHA&stage=qc_testing&q=RM')
  expect(screen.getByText('Type: Peptides')).toBeInTheDocument()
  expect(screen.getByText('Campaign: CMP-ALPHA')).toBeInTheDocument()
  expect(screen.getByText('Stage: qc_testing')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
  expect(screen.getByTestId('url')).toHaveTextContent('')
  expect(screen.queryByTestId('filter-chips')).not.toBeInTheDocument()
})

test('F16-FR-02: "All" clears a row and values within a row are ORed in the URL', async () => {
  renderAt('/overview?filters=open&type=peptide')
  const types = within(screen.getByRole('group', { name: 'Type' }))
  expect(types.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false')
  await userEvent.click(types.getByRole('button', { name: 'Large Molecule' }))
  expect(screen.getByTestId('url')).toHaveTextContent(/type=peptide&type=large_molecule/)
  await userEvent.click(types.getByRole('button', { name: 'All' }))
  expect(screen.getByTestId('url')).not.toHaveTextContent('type=')
  expect(types.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true')
})

test('F16-FR-02 / OQ-086: the Unknown class pill is always there, with its count, and uses the key "unknown"', async () => {
  renderAt('/overview?filters=open')
  const unknown = within(screen.getByRole('group', { name: 'Class' })).getByRole('button', { name: /Unknown/ })
  expect(unknown).toHaveTextContent('2')
  await userEvent.click(unknown)
  expect(screen.getByTestId('url')).toHaveTextContent('class=unknown')
})

test('F16-FR-02: campaign pills show live counts, filter by the search box and scroll in at most three rows', async () => {
  renderAt('/overview?filters=open')
  const pills = within(screen.getByTestId('campaign-pills'))
  expect(pills.getByRole('button', { name: /CMP-ALPHA/ })).toHaveTextContent('2')
  expect(pills.getByRole('button', { name: /CMP-CHARLIE/ })).toHaveTextContent('0')
  expect(screen.getByTestId('campaign-pills').className).toContain('overflow-y-auto')
  await userEvent.type(screen.getByRole('searchbox', { name: 'Filter campaigns' }), 'brav')
  expect(pills.queryByRole('button', { name: /CMP-ALPHA/ })).not.toBeInTheDocument()
  await userEvent.click(pills.getByRole('button', { name: /CMP-BRAVO/ }))
  expect(screen.getByTestId('url')).toHaveTextContent('campaign=CMP-BRAVO')
})

test('F16-FR-02: the Dropdown view turns the campaign pills into one multi-select and is remembered for the session', async () => {
  const first = renderAt('/overview?filters=open')
  await userEvent.click(screen.getByRole('button', { name: '▤ Dropdown view' }))
  expect(screen.queryByTestId('campaign-pills')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /All campaigns/ }))
  await userEvent.click(screen.getByRole('checkbox', { name: /CMP-BRAVO/ }))
  expect(screen.getByTestId('url')).toHaveTextContent('campaign=CMP-BRAVO')
  expect(sessionStorage.getItem('r2r.campaignView')).toBe('dropdown')
  first.unmount()
  renderAt('/overview?filters=open')
  expect(screen.queryByTestId('campaign-pills')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /All campaigns/ })).toBeInTheDocument()
})

test('F17-FR-08: tags in the URL appear as filter chips when the panel is closed, and removing one updates the URL', async () => {
  renderAt('/overview?flag=on_hold&flag=ud_rejected&flag=lims_rejected')
  expect(screen.getByText('Tag: ON HOLD')).toBeInTheDocument()
  expect(screen.getByText('Tag: REJECTED')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Remove Tag: ON HOLD' }))
  expect(screen.getByTestId('url')).not.toHaveTextContent('on_hold')
})

test('F17-AC-02: each selected stage is its own chip, and removing one keeps the others in the URL', async () => {
  renderAt('/overview?stage=sampling&stage=qc_ship&stage=qc_testing')
  for (const key of ['sampling', 'qc_ship', 'qc_testing']) expect(screen.getByText(`Stage: ${key}`)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Remove Stage: qc_ship' }))
  expect(screen.getByTestId('url')).toHaveTextContent('stage=sampling&stage=qc_testing')
  expect(screen.getByTestId('url')).not.toHaveTextContent('qc_ship')
})

test('F15-FR-05: Type options show the labels from the reference, not the keys', async () => {
  renderAt('/overview?filters=open')
  expect(within(screen.getByRole('group', { name: 'Type' })).getByRole('button', { name: 'Peptides' })).toBeInTheDocument()
  expect(screen.queryByText('small_molecule')).not.toBeInTheDocument()
})

test('F16-AC-02: Bookmarked is greyed until the user has a bookmark, then toggles bookmarked=1 in the URL', async () => {
  const first = renderAt()
  expect(screen.getByRole('button', { name: /^[☆★] Bookmarked$/ })).toBeDisabled()
  first.unmount()
  renderAt('/overview', ['RM1|B1|1', 'RM2|B2|1'])
  const button = screen.getByRole('button', { name: /^[☆★] Bookmarked$/ })
  expect(button).toBeEnabled()
  await userEvent.click(button)
  expect(screen.getByTestId('url')).toHaveTextContent('bookmarked=1')
  expect(screen.getByRole('button', { name: /^[☆★] Bookmarked$/ })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('Bookmarked', { selector: 'span' })).toBeInTheDocument() // the chip
  await userEvent.click(screen.getByRole('button', { name: 'Remove Bookmarked' }))
  expect(screen.getByTestId('url')).not.toHaveTextContent('bookmarked')
})

test('F16-FR-04: with the filter on and no bookmarks left, the button stays usable so it can be switched off', () => {
  renderAt('/overview?bookmarked=1', [])
  expect(screen.getByRole('button', { name: /^[☆★] Bookmarked$/ })).toBeEnabled()
})

test('two pills clicked before React re-renders both count (F16-AC-01)', async () => {
  renderAt('/overview?filters=open')
  const classes = within(screen.getByRole('group', { name: 'Class' }))
  // Both clicks run inside one act(), so the second arrives before the first has re-rendered the pills.
  act(() => {
    fireEvent.click(classes.getByRole('button', { name: 'Consumable' }))
    fireEvent.click(classes.getByRole('button', { name: 'Drug Substance' }))
  })
  expect(screen.getByTestId('url')).toHaveTextContent('class=consumable&class=drug_substance')
})

test('collapsing the panel right after a pill keeps the pill (F16-AC-01)', () => {
  renderAt('/overview?filters=open')
  act(() => {
    fireEvent.click(within(screen.getByRole('group', { name: 'Class' })).getByRole('button', { name: 'Consumable' }))
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))
  })
  expect(screen.getByTestId('url')).toHaveTextContent('class=consumable')
  expect(screen.getByTestId('url')).toHaveTextContent('filters=closed')
})
