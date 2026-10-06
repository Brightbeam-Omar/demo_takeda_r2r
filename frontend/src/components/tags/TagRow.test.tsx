import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { expect, test } from 'vitest'
import { DEFAULT_TERMS } from '../../hooks/useTerms'
import { showingText } from '../../lib/tags'
import { EMPTY_FILTERS, useUrlFilters } from '../../state/url-filters'
import { renderWithProviders } from '../../test-utils'
import { ShowingLine, TagRow } from './TagRow'

function Harness() {
  const { filters, update } = useUrlFilters()
  const location = useLocation()
  return (
    <>
      <ShowingLine filters={filters} />
      <TagRow filters={filters} onChange={update} />
      <output data-testid="url">{location.search}</output>
    </>
  )
}

const renderAt = (entry = '/overview') =>
  renderWithProviders(
    <MemoryRouter initialEntries={[entry]}>
      <Harness />
    </MemoryRouter>,
  )

test('F17-FR-08: the tag row lists ALL then the eleven tags in order, with the profile term for the blocked tag', () => {
  renderAt()
  const labels = screen.getAllByRole('button').map((button) => button.textContent)
  expect(labels).toEqual([
    'ALL', 'LATE', 'ON HOLD', 'REJECTED', 'RE-EVAL', 'EXPEDITE', 'FULL SPEC', 'OFFSITE TEST', 'RELEASE ON COA', 'ERP BLOCKED', 'AIR GAP', 'RELEASED',
  ])
  expect(screen.getByTestId('tag-all')).toHaveAttribute('aria-pressed', 'true')
  expect(screen.queryByRole('button', { name: 'Clear tags' })).not.toBeInTheDocument()
})

test('F17-AC-05: ON HOLD + EXPEDITE are ORed in the URL, fill solid, switch ALL off, and Clear tags restores everything', async () => {
  renderAt()
  await userEvent.click(screen.getByTestId('tag-on_hold'))
  await userEvent.click(screen.getByTestId('tag-expedite'))
  expect(screen.getByTestId('url')).toHaveTextContent('flag=on_hold&flag=expedite')
  expect(screen.getByTestId('tag-on_hold')).toHaveClass('bg-red-700', 'text-white')
  expect(screen.getByTestId('tag-expedite')).toHaveClass('bg-orange-700', 'text-white')
  expect(screen.getByTestId('tag-late')).not.toHaveClass('bg-red-600')
  expect(screen.getByTestId('tag-all')).toHaveAttribute('aria-pressed', 'false')
  expect(screen.getByTestId('showing-line')).toHaveTextContent('Showing: 2 tags')
  await userEvent.click(screen.getByRole('button', { name: 'Clear tags' }))
  expect(screen.getByTestId('url')).not.toHaveTextContent('flag=')
  expect(screen.getByTestId('tag-all')).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByTestId('showing-line')).toHaveTextContent('Showing: All in-flight batches')
})

test('F17-FR-08: REJECTED sets both rejection flags and a second click removes them; ALL clears the tags', async () => {
  renderAt()
  await userEvent.click(screen.getByTestId('tag-rejected'))
  expect(screen.getByTestId('url')).toHaveTextContent('flag=ud_rejected&flag=lims_rejected')
  await userEvent.click(screen.getByTestId('tag-rejected'))
  expect(screen.getByTestId('url')).not.toHaveTextContent('flag=')
  await userEvent.click(screen.getByTestId('tag-released'))
  await userEvent.click(screen.getByTestId('tag-all'))
  expect(screen.getByTestId('url')).not.toHaveTextContent('flag=')
})

test('F17-FR-07: the showing line summarises stages, tags and bookmarks', () => {
  const filters = { ...EMPTY_FILTERS }
  expect(showingText(filters, DEFAULT_TERMS)).toBe('All in-flight batches')
  expect(showingText({ ...filters, stages: ['a', 'b', 'c'], flags: ['late', 'on_hold'] }, DEFAULT_TERMS)).toBe('3 stages selected · 2 tags')
  expect(showingText({ ...filters, stages: ['a'], bookmarked: true }, DEFAULT_TERMS)).toBe('1 stage selected · bookmarked')
  expect(showingText({ ...filters, types: ['peptide'] }, DEFAULT_TERMS)).toBe('All in-flight batches') // type and class have their own chips
})
