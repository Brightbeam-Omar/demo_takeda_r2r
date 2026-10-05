import { expect, test } from 'vitest'
import { addMonths, monthGrid } from './calendar'

test('F10-FR-05: October 2026 starts on a Thursday in a Monday-first grid', () => {
  const grid = monthGrid(2026, 9)
  expect(grid[0]).toEqual([null, null, null, '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'])
  expect(grid.flat().filter(Boolean)).toHaveLength(31)
  expect(addMonths(2026, 11, 1)).toEqual({ year: 2027, month: 0 })
})
