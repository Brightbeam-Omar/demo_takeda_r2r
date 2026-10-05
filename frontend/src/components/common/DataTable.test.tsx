import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import * as download from '../../lib/download'
import { DataTable, type Column } from './DataTable'

interface Item {
  id: string
  name: string
  days: number
}
const items: Item[] = Array.from({ length: 23 }, (_, n) => ({ id: `i${n}`, name: n === 7 ? 'Special, "quoted"' : `Item ${n}`, days: n === 7 ? 100 : n }))
const columns: Column<Item>[] = [
  { id: 'name', header: 'Name', cell: (r) => r.name, text: (r) => r.name },
  { id: 'days', header: 'Days', cell: (r) => `${r.days} d`, text: (r) => `${r.days} d`, sortValue: (r) => r.days },
]
const show = (rows = items) => render(<DataTable rows={rows} columns={columns} exportName="things" rowKey={(r) => r.id} />)
const names = () => screen.getAllByTestId('window-row').map((row) => within(row).getAllByRole('cell')[0]!.textContent)

afterEach(() => vi.restoreAllMocks())

test('F16-FR-07: pages of 10 by default, with the range, page count and next/previous', async () => {
  show()
  expect(screen.getAllByTestId('window-row')).toHaveLength(10)
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–10 of 23')
  expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
  await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
  expect(screen.getByTestId('page-summary')).toHaveTextContent('21–23 of 23')
  expect(screen.getAllByTestId('window-row')).toHaveLength(3)
  expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
})

test('F16-FR-07: rows per page changes the page size', async () => {
  show()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Rows per page' }), '25')
  expect(screen.getAllByTestId('window-row')).toHaveLength(23)
  expect(screen.getByText('Page 1 of 1')).toBeInTheDocument()
})

test('F16-FR-07: Search all columns narrows the rows by what the cells show, and Reset Table undoes it with the sort', async () => {
  show()
  await userEvent.type(screen.getByRole('searchbox', { name: 'Search all columns' }), '100 d')
  expect(names()).toEqual(['Special, "quoted"'])
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–1 of 1')
  await userEvent.click(screen.getByRole('button', { name: 'Days' }))
  await userEvent.click(screen.getByRole('button', { name: 'Reset Table' }))
  expect(screen.getByRole('searchbox', { name: 'Search all columns' })).toHaveValue('')
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–10 of 23')
  expect(names()[0]).toBe('Item 0')
  expect(screen.getByRole('columnheader', { name: /Days/ })).toHaveAttribute('aria-sort', 'none')
})

test('F16-FR-07: a numeric column sorts by its sort value, not its text', async () => {
  show()
  await userEvent.click(screen.getByRole('button', { name: 'Days' }))
  expect(names().slice(0, 3)).toEqual(['Special, "quoted"', 'Item 22', 'Item 21']) // numbers sort largest first; 100 is not 'Item 9'
  await userEvent.click(screen.getByRole('button', { name: 'Days' }))
  expect(names().slice(0, 3)).toEqual(['Item 0', 'Item 1', 'Item 2']) // then ascending (text order would put "1 d", "10 d" first)
})

test('F16-FR-07: Export saves every matching row, not just the page, with the CSV quoting', async () => {
  const save = vi.spyOn(download, 'saveBlob').mockImplementation(() => undefined)
  show()
  await userEvent.click(screen.getByRole('button', { name: 'Export' }))
  const [blob, filename] = save.mock.calls[0]!
  expect(filename).toBe('things.csv')
  const lines = (await blob.text()).trim().split('\n')
  expect(lines).toHaveLength(24) // header + 23 rows, although only 10 are on the page
  expect(lines[0]).toBe('Name,Days')
  expect(lines).toContain('"Special, ""quoted""",100 d')
})

test('F16-FR-07: with no rows it shows the empty text', () => {
  render(<DataTable rows={[]} columns={columns} exportName="things" rowKey={(r: Item) => r.id} empty="Nothing here." />)
  expect(screen.getByText('Nothing here.')).toBeInTheDocument()
})
