import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { Row } from '../../api/queries'
import { AdjustedNeedBy, Light, MaterialCell, RagCell, SystemNeedBy } from './cells'

const base = {
  row_key: 'RM10023|B1042|10000042',
  material_no: 'RM10023',
  material_desc: 'Excipient 017',
  system_need_by_locked: '2026-12-03',
  adjusted_need_by_date: null,
  flags: { on_hold: true, ud_rejected: false, lims_rejected: true, air_gap: false },
  plan: { expected_completion: '2026-10-15', rag: 'green', days_remaining: 3 },
} as unknown as Row

test('F10-AC-07: an overridden need-by is italic with the system date struck through', () => {
  const row = { ...base, adjusted_need_by_date: '2026-11-26' } as Row
  render(
    <>
      <SystemNeedBy row={row} />
      <AdjustedNeedBy row={row} canEdit />
    </>,
  )
  expect(screen.getByTestId('system-need-by')).toHaveClass('line-through')
  expect(screen.getByTestId('adjusted-need-by')).toHaveClass('italic')
  expect(screen.getByTestId('adjusted-need-by')).toHaveTextContent('26 Nov')
  // An overridden need-by always shows its pencil.
  expect(screen.getByRole('button', { name: 'Edit need-by' })).not.toHaveClass('opacity-0')
})

test('F10-AC-07: without an override the system date is plain; the pencil is disabled for read-only roles', () => {
  render(
    <>
      <SystemNeedBy row={base} />
      <AdjustedNeedBy row={base} canEdit={false} />
    </>,
  )
  expect(screen.getByTestId('system-need-by')).not.toHaveClass('line-through')
  const pencil = screen.getByRole('button', { name: 'Edit need-by' })
  expect(pencil).toBeDisabled()
  expect(pencil).toHaveAttribute('title', 'Read-only role')
  // Without an override the pencil only appears on row hover.
  expect(pencil).toHaveClass('opacity-0', 'group-hover:opacity-100')
})

test('F10-AC-07: the RAG cell shows the date, days remaining and the colour; tag chips and lights read as text', () => {
  render(
    <>
      <RagCell row={base} />
      <MaterialCell row={base} />
      <Light colour="red" what="Deviations" />
    </>,
  )
  expect(screen.getByTestId('rag-cell')).toHaveTextContent('15 Oct · 3 d')
  expect(screen.getByTestId('rag-cell')).toHaveAttribute('data-rag', 'green')
  expect(screen.getByText('HOLD')).toBeInTheDocument()
  expect(screen.getByText('REJECTED')).toBeInTheDocument()
  expect(screen.queryByText('AIR GAP')).not.toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Deviations: red' })).toBeInTheDocument()
})
