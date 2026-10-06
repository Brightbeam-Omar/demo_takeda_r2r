import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Row } from '../../api/queries'
import { BookmarkStar, Light, TagChips } from './cells'

const base = {
  flags: { on_hold: true, ud_rejected: false, lims_rejected: true, air_gap: false },
} as unknown as Row

test('F10-AC-07: tag chips and lights read as text', () => {
  render(
    <>
      <TagChips flags={base.flags} />
      <Light colour="red" what="Deviations" />
    </>,
  )
  expect(screen.getByText('HOLD')).toBeInTheDocument()
  expect(screen.getByText('REJECTED')).toBeInTheDocument()
  expect(screen.queryByText('AIR GAP')).not.toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Deviations: red' })).toBeInTheDocument()
})

test('F16-FR-04: the star bookmarks without bubbling to the row, and stays out of the Tab order', async () => {
  const toggle = vi.fn()
  const row = vi.fn()
  render(
    <div onClick={row}>
      <BookmarkStar rowKey="RM1|B1|1" on={false} onToggle={toggle} />
    </div>,
  )
  const star = screen.getByRole('button', { name: 'Bookmark RM1|B1|1' })
  expect(star).toHaveAttribute('tabindex', '-1')
  await userEvent.click(star)
  expect(toggle).toHaveBeenCalledWith('RM1|B1|1', true)
  expect(row).not.toHaveBeenCalled()
})
