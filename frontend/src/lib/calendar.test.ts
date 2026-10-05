import { expect, test } from 'vitest'
import { addMonths, isoWeek, monthGrid } from './calendar'

test('F10-FR-05: October 2026 starts on a Thursday in a Monday-first grid', () => {
  const grid = monthGrid(2026, 9)
  expect(grid[0]).toEqual([null, null, null, '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'])
  expect(grid.flat().filter(Boolean)).toHaveLength(31)
  expect(addMonths(2026, 11, 1)).toEqual({ year: 2027, month: 0 })
})

test('F17-FR-06: isoWeek gives the ISO week and week-year, including at the year boundaries', () => {
  expect(isoWeek('2026-10-05')).toEqual({ week: 41, year: 2026 })
  expect(isoWeek('2026-10-11')).toEqual({ week: 41, year: 2026 })
  expect(isoWeek('2026-10-12')).toEqual({ week: 42, year: 2026 })
  expect(isoWeek('2026-01-01')).toEqual({ week: 1, year: 2026 })
  expect(isoWeek('2021-01-03')).toEqual({ week: 53, year: 2020 })
  expect(isoWeek('2024-12-30')).toEqual({ week: 1, year: 2025 })
})
