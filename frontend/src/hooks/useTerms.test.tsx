import { screen } from '@testing-library/react'
import { renderWithProviders } from '../test-utils'
import { expect, test } from 'vitest'
import { FilterBar } from '../components/filters/FilterBar'
import { DEFAULT_TERMS, TermsContext } from './useTerms'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

vi.stubGlobal('fetch', vi.fn(async () => new Response('[]')))

function band(erpBlockedTag: string) {
  renderWithProviders(
    <MemoryRouter>
      <TermsContext.Provider value={{ ...DEFAULT_TERMS, erp_blocked_tag: erpBlockedTag }}>
        <FilterBar
          reference={undefined}
          rows={[]}
          filters={{
            types: [],
            classes: [],
            campaigns: [],
            flags: [],
            stages: [],
            bookmarked: false,
            q: '',
            period: 'all',
            from: null,
            to: null,
          }}
          stageLabel={(key) => key}
          bookmarks={[]}
          onChange={vi.fn()}
          onClear={vi.fn()}
        />
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
