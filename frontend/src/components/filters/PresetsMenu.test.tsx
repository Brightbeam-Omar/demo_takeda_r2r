import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Preset } from '../../api/queries'
import { useUrlFilters } from '../../state/url-filters'
import { renderWithProviders } from '../../test-utils'
import { PresetsMenu } from './PresetsMenu'

/** An in-memory /api/presets: a duplicate name is 409, PUT replaces the query. */
function fakePresetApi(store: Preset[]) {
  let nextId = 1
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const id = /\/api\/presets\/(\d+)/.exec(url)?.[1]
      if (method === 'GET') return json(store)
      if (method === 'POST') {
        const body = JSON.parse(String(init?.body)) as { name: string; query: string }
        if (store.some((preset) => preset.name === body.name)) return json({ detail: 'duplicate' }, 409)
        const created = { id: nextId++, ...body, created_at: '2026-10-12T07:00:00Z' }
        store.push(created)
        return json(created, 201)
      }
      if (method === 'PUT') {
        const preset = store.find((item) => item.id === Number(id))!
        preset.query = (JSON.parse(String(init?.body)) as { query: string }).query
        return json(preset)
      }
      store.splice(store.findIndex((item) => item.id === Number(id)), 1)
      return new Response(null, { status: 204 })
    }),
  )
}

function Harness() {
  const { filters, update, clearAll } = useUrlFilters()
  const location = useLocation()
  return (
    <>
      <PresetsMenu filters={filters} onApply={update} />
      <button type="button" onClick={clearAll}>
        clear
      </button>
      <output data-testid="url">{location.search}</output>
    </>
  )
}

let store: Preset[]
beforeEach(() => {
  store = []
  fakePresetApi(store)
})
afterEach(() => vi.unstubAllGlobals())

const open = async (entry = '/overview?type=small_molecule&class=consumable&period=this_week') => {
  renderWithProviders(
    <MemoryRouter initialEntries={[entry]}>
      <Harness />
    </MemoryRouter>,
  )
  await userEvent.click(screen.getByRole('button', { name: /Presets/ }))
}

async function save(name: string) {
  await userEvent.click(screen.getByRole('menuitem', { name: '+ Save current filters' }))
  await userEvent.type(screen.getByRole('textbox', { name: 'Preset name' }), name)
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
}

test('F16-FR-05: an empty menu says "No saved presets" and offers + Save current filters', async () => {
  await open()
  expect(await screen.findByText('No saved presets')).toBeInTheDocument()
  expect(screen.getByRole('menuitem', { name: '+ Save current filters' })).toBeInTheDocument()
})

test('F16-AC-03: save, clear everything, apply: the URL filters come back and the period stays relative', async () => {
  await open()
  await save('My small molecules')
  await waitFor(() => expect(store).toHaveLength(1))
  expect(store[0]!.query).toBe('type=small_molecule&class=consumable&period=this_week')

  await userEvent.click(screen.getByRole('button', { name: 'clear' }))
  expect(screen.getByTestId('url')).not.toHaveTextContent('small_molecule')

  await userEvent.click(screen.getByRole('button', { name: /Presets/ }))
  await userEvent.click(await screen.findByRole('menuitem', { name: 'My small molecules' }))
  expect(screen.getByTestId('url')).toHaveTextContent('type=small_molecule&class=consumable&period=this_week')
})

test('F16-FR-05: applying a preset replaces the filter state rather than adding to it', async () => {
  store.push({ id: 7, name: 'Peptides', query: 'type=peptide', created_at: '2026-10-12T07:00:00Z' })
  await open('/overview?type=small_molecule&campaign=CMP-ALPHA')
  await userEvent.click(await screen.findByRole('menuitem', { name: 'Peptides' }))
  const url = screen.getByTestId('url')
  expect(url).toHaveTextContent('type=peptide')
  expect(url).not.toHaveTextContent('small_molecule')
  expect(url).not.toHaveTextContent('campaign')
})

test('F16-OQ-089: a duplicate name asks "Replace existing preset?" and confirming overwrites it through PUT', async () => {
  store.push({ id: 3, name: 'Mine', query: 'type=peptide', created_at: '2026-10-12T07:00:00Z' })
  await open()
  await save('Mine')
  expect(await screen.findByRole('alertdialog', { name: 'Replace existing preset?' })).toBeInTheDocument()
  expect(store[0]!.query).toBe('type=peptide') // nothing replaced yet
  await userEvent.click(screen.getByRole('button', { name: 'Replace' }))
  await waitFor(() => expect(store[0]!.query).toBe('type=small_molecule&class=consumable&period=this_week'))
  expect(store).toHaveLength(1)
})

test('F16-OQ-089: cancelling the replacement leaves the preset alone', async () => {
  store.push({ id: 3, name: 'Mine', query: 'type=peptide', created_at: '2026-10-12T07:00:00Z' })
  await open()
  await save('Mine')
  await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
  expect(store[0]!.query).toBe('type=peptide')
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})

test('F16-FR-05: a preset can be deleted from the menu', async () => {
  store.push({ id: 3, name: 'Mine', query: 'type=peptide', created_at: '2026-10-12T07:00:00Z' })
  await open()
  await userEvent.click(await screen.findByRole('button', { name: 'Delete preset Mine' }))
  await waitFor(() => expect(store).toHaveLength(0))
  expect(await screen.findByText('No saved presets')).toBeInTheDocument()
})
