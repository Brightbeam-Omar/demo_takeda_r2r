import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as download from '../../lib/download'
import { DataTable, type Column } from './DataTable'

interface Item {
  id: string
  name: string
  days: number
  note: string
}
const items: Item[] = Array.from({ length: 120 }, (_, n) => ({
  id: `i${n}`,
  name: n === 7 ? 'Special, "quoted"' : `Item ${n}`,
  days: n === 7 ? 1000 : n,
  note: `B20${n}`,
}))
const columns: Column<Item>[] = [
  { id: 'name', header: 'Name', cell: (r, { hl }) => hl(r.name), text: (r) => r.name },
  { id: 'days', header: 'Days', cell: (r) => `${r.days}d`, text: (r) => `${r.days}d`, sortValue: (r) => r.days },
  { id: 'note', header: 'Note', cell: (r, { hl }) => hl(r.note), text: (r) => r.note },
  { id: 'extra', header: 'Extra', cell: () => 'x', text: () => 'extra text', defaultHidden: true },
]
const show = (props: Partial<Parameters<typeof DataTable<Item>>[0]> = {}) =>
  render(<DataTable rows={items} columns={columns} exportName="things" rowKey={(r) => r.id} unit={['lot', 'lots']} {...props} />)
const names = () => screen.getAllByTestId('window-row').map((row) => within(row).getAllByRole('cell')[0]!.textContent)

beforeEach(() => sessionStorage.clear())
afterEach(() => vi.restoreAllMocks())

test('F18-FR-01: 50 rows per page by default, with « ‹ Prev, Page x of y, Next › » and 25/50/100', async () => {
  show()
  expect(screen.getAllByTestId('window-row')).toHaveLength(50)
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–50 of 120 lots')
  expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Last page' }))
  expect(screen.getByTestId('page-summary')).toHaveTextContent('101–120 of 120 lots')
  expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual(['25', '50', '100'])
  await userEvent.click(screen.getByRole('button', { name: 'First page' }))
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Rows per page' }), '100')
  expect(screen.getAllByTestId('window-row')).toHaveLength(100)
})

test('F18-FR-01: the toolbar is repeated above and below the table', () => {
  show()
  expect(screen.getByTestId('table-toolbar-top')).toBeInTheDocument()
  expect(screen.getByTestId('table-toolbar-bottom')).toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: /Reset Table/ })).toHaveLength(2)
})

test('F18-FR-01: every header has an always-visible filter box that narrows on the displayed text', async () => {
  show()
  await userEvent.type(screen.getByRole('textbox', { name: 'Filter Name' }), 'item 11')
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–11 of 11 lots') // Item 11, Item 110..119
  expect(screen.getByRole('textbox', { name: 'Filter Days' })).toBeVisible()
})

test('F18-FR-01: a numeric column sorts by its sort value; Reset Table clears sort and column filters but keeps the search', async () => {
  show()
  await userEvent.click(screen.getByRole('button', { name: 'Days' }))
  expect(names()[0]).toBe('Special, "quoted"') // 1000 is largest; text order would not put it first
  await userEvent.type(screen.getByRole('textbox', { name: 'Filter Name' }), 'Item')
  await userEvent.type(screen.getAllByRole('textbox', { name: 'Search all columns' })[0]!, 'B20')
  await userEvent.click(screen.getAllByRole('button', { name: /Reset Table/ })[0]!)
  expect(screen.getByRole('textbox', { name: 'Filter Name' })).toHaveValue('')
  expect(screen.getByRole('columnheader', { name: /Days/ })).toHaveAttribute('aria-sort', 'none')
  expect(screen.getAllByRole('textbox', { name: 'Search all columns' })[0]).toHaveValue('B20')
})

test('F18-FR-02: Columns lists every column, defaults the hidden one off, adds it on tick and restores with Reset', async () => {
  show()
  expect(screen.queryByRole('columnheader', { name: /Extra/ })).not.toBeInTheDocument()
  await userEvent.click(screen.getAllByRole('button', { name: /Columns/ })[0]!)
  const panel = screen.getByRole('group', { name: 'Columns' })
  expect(within(panel).getAllByRole('checkbox')).toHaveLength(4)
  await userEvent.click(within(panel).getByRole('checkbox', { name: 'Extra' }))
  expect(screen.getByRole('columnheader', { name: /Extra/ })).toBeInTheDocument()
  await userEvent.click(within(panel).getByRole('button', { name: 'Reset' }))
  expect(screen.queryByRole('columnheader', { name: /Extra/ })).not.toBeInTheDocument()
})

test('F18-FR-02: the column choice persists in sessionStorage per key', async () => {
  const first = show({ columnsKey: 'overview.pat' })
  await userEvent.click(screen.getAllByRole('button', { name: /Columns/ })[0]!)
  await userEvent.click(within(screen.getByRole('group', { name: 'Columns' })).getByRole('checkbox', { name: 'Extra' }))
  first.unmount()
  show({ columnsKey: 'overview.pat' })
  expect(screen.getByRole('columnheader', { name: /Extra/ })).toBeInTheDocument()
  screen.getByRole('columnheader', { name: /Extra/ }).closest('table')?.remove()
})

test('F18-FR-02: a different persona key starts from the defaults', () => {
  sessionStorage.setItem('r2r.columns.overview.pat', JSON.stringify(['name', 'extra']))
  show({ columnsKey: 'overview.sam' })
  expect(screen.queryByRole('columnheader', { name: /Extra/ })).not.toBeInTheDocument()
})

test('F18-FR-05: search narrows over every visible column and marks each match; the × clears it', async () => {
  function Controlled() {
    const [value, setValue] = useState('')
    return <DataTable rows={items} columns={columns} exportName="things" rowKey={(r) => r.id} unit={['lot', 'lots']} search={{ value, onChange: setValue }} />
  }
  render(<Controlled />)
  await userEvent.type(screen.getAllByRole('textbox', { name: 'Search all columns' })[0]!, 'b20119')
  expect(screen.getAllByTestId('window-row')).toHaveLength(1)
  const marks = document.querySelectorAll('mark')
  expect(marks).toHaveLength(1)
  expect(marks[0]).toHaveTextContent('B20119')
  await userEvent.click(screen.getAllByRole('button', { name: 'Clear search' })[0]!)
  expect(document.querySelectorAll('mark')).toHaveLength(0)
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–50 of 120 lots')
})

test('F18-FR-05: a hidden column is not searched', async () => {
  show()
  await userEvent.type(screen.getAllByRole('textbox', { name: 'Search all columns' })[0]!, 'extra text')
  expect(screen.getByTestId('page-summary')).toHaveTextContent('No results')
  expect(screen.getByText('No results', { selector: 'p' })).toBeInTheDocument()
})

test('F18-FR-06: the count takes an optional suffix, and an empty table says No results', async () => {
  show({ countSuffix: (rows) => ` (${new Set(rows.map((r) => r.note.slice(0, 3))).size} batches)` })
  expect(screen.getByTestId('page-summary')).toHaveTextContent('1–50 of 120 lots (1 batches)')
})

test('F18-FR-07: Export offers This page and All filtered results, built from the visible columns', async () => {
  const save = vi.spyOn(download, 'saveBlob').mockImplementation(() => undefined)
  show()
  await userEvent.type(screen.getAllByRole('textbox', { name: 'Search all columns' })[0]!, 'Item 1')
  await userEvent.click(screen.getAllByRole('button', { name: /Export/ })[0]!)
  expect(screen.getByRole('menuitem', { name: 'This page (31 rows)' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('menuitem', { name: 'All filtered results (31 rows)' }))
  const blob = save.mock.calls[0]![0]
  const lines = (await blob.text()).trim().split('\n')
  expect(lines[0]).toBe('Name,Days,Note')
  expect(lines).toHaveLength(32)
  expect(save.mock.calls[0]![1]).toBe('things-filtered.csv')
})

test('F18-FR-11: Tab focuses the table, ↓↓ then Enter opens the third row, B reaches the handler', async () => {
  const open = vi.fn()
  const key = vi.fn()
  show({ onRowOpen: open, onRowKey: key, keyboardHint: 'Keyboard: ↑ ↓ Enter B' })
  const grid = screen.getByRole('grid')
  grid.focus()
  expect(grid).toHaveFocus()
  await userEvent.keyboard('{ArrowDown}{ArrowDown}')
  expect(screen.getAllByTestId('window-row')[2]).toHaveAttribute('data-active', 'true')
  await userEvent.keyboard('b')
  expect(key).toHaveBeenCalledWith('b', items[2])
  await userEvent.keyboard('{Enter}')
  expect(open).toHaveBeenCalledWith(items[2])
  expect(screen.getByTestId('keyboard-hint')).toHaveTextContent('Keyboard')
})

test('F18-FR-11: shortcuts do nothing while a text box has focus', async () => {
  const key = vi.fn()
  show({ onRowKey: key })
  await userEvent.type(screen.getAllByRole('textbox', { name: 'Search all columns' })[0]!, 'b')
  expect(key).not.toHaveBeenCalled()
})

test('F18-FR-01: the first column is sticky so the rest can scroll sideways', () => {
  show()
  expect(screen.getAllByRole('cell')[0]).toHaveClass('sticky')
})
