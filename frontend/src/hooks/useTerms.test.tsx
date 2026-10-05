import { screen } from '@testing-library/react'
import { renderWithProviders } from '../test-utils'
import { expect, test } from 'vitest'
import { TagRow } from '../components/tags/TagRow'
import { EMPTY_FILTERS } from '../state/url-filters'
import { DEFAULT_TERMS, TermsContext } from './useTerms'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

vi.stubGlobal('fetch', vi.fn(async () => new Response('[]')))

function band(erpBlockedTag: string) {
  renderWithProviders(
    <MemoryRouter>
      <TermsContext.Provider value={{ ...DEFAULT_TERMS, erp_blocked_tag: erpBlockedTag }}>
        <TagRow filters={EMPTY_FILTERS} onChange={vi.fn()} />
      </TermsContext.Provider>
    </MemoryRouter>,
  )
}

test('F15-AC-03: the blocked tag comes from the terms, with no code change between profiles', () => {
  band('SAP BLOCKED')
  expect(screen.getByRole('button', { name: 'SAP BLOCKED' })).toBeInTheDocument()
})

test('F15-AC-03: a profile whose erp term is ERP reads ERP BLOCKED', () => {
  band('ERP BLOCKED')
  expect(screen.getByRole('button', { name: 'ERP BLOCKED' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'SAP BLOCKED' })).not.toBeInTheDocument()
})
