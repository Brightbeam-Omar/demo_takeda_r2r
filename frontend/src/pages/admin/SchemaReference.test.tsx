import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test-utils'
import { SchemaReference } from './SchemaReference'

afterEach(() => vi.unstubAllGlobals())

const schema = {
  objects: [
    {
      name: 'batch_pipeline_v',
      description: 'The pipeline.',
      grain: 'One row per lot.',
      columns: [
        { name: 'row_key', type: 'string', description: 'Key of the lot.' },
        { name: 'stage_key', type: 'string', description: 'The stage the lot is in now.' },
      ],
    },
    {
      name: 'pipeline_runs_v',
      description: 'The run history.',
      grain: 'One row per pipeline run.',
      columns: [{ name: 'skipped', type: 'integer', description: 'Rows unchanged since the previous run.' }],
    },
  ],
}

function setup() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (url.startsWith('/api/schema') ? new Response(JSON.stringify(schema)) : new Response('nf', { status: 404 }))))
  renderWithProviders(
    <MemoryRouter>
      <SchemaReference />
    </MemoryRouter>,
  )
}

test('F21-AC-06: every published object is listed with its description and grain', async () => {
  setup()
  const objects = await screen.findAllByTestId('schema-object')
  expect(objects).toHaveLength(2)
  expect(objects[0]).toHaveTextContent('batch_pipeline_v')
  expect(objects[0]).toHaveTextContent('2 columns')
  expect(objects[1]).toHaveTextContent('Grain: One row per pipeline run.')
})

test('F21-FR-06: an object opens to its columns with type and description', async () => {
  setup()
  const [first] = await screen.findAllByTestId('schema-object')
  expect(within(first).queryByTestId('schema-columns')).not.toBeInTheDocument()
  await userEvent.click(within(first).getByRole('button'))
  const columns = within(first).getAllByTestId('schema-column')
  expect(columns[1]).toHaveTextContent('stage_key')
  expect(columns[1]).toHaveTextContent('string')
  expect(columns[1]).toHaveTextContent('The stage the lot is in now.')
})

test('F21-FR-06: searching narrows to the objects and columns that match', async () => {
  setup()
  await screen.findAllByTestId('schema-object')
  await userEvent.type(screen.getByLabelText('Search the schema'), 'skipped')
  const objects = screen.getAllByTestId('schema-object')
  expect(objects).toHaveLength(1)
  expect(objects[0]).toHaveAttribute('data-object', 'pipeline_runs_v')
  expect(within(objects[0]).getAllByTestId('schema-column')).toHaveLength(1)
  await userEvent.clear(screen.getByLabelText('Search the schema'))
  await userEvent.type(screen.getByLabelText('Search the schema'), 'zzz')
  expect(screen.getByText(/Nothing matches/)).toBeInTheDocument()
})
