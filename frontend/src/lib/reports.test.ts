import { expect, test } from 'vitest'
import { dayLabel, fillPercent, formatPct, isoWeek, isTab, markerPercent, monthLabel, trendView, weekLabel } from './reports'

test('F20-FR-05: ISO weeks match the pipeline (week 41 of 2026 starts on 5 Oct)', () => {
  expect(isoWeek('2026-10-05')).toBe(41)
  expect(isoWeek('2026-10-11')).toBe(41)
  expect(isoWeek('2026-10-12')).toBe(42)
  expect(isoWeek('2025-12-29')).toBe(1) // the week of 1 Jan 2026
  expect(isoWeek('2027-01-03')).toBe(53)
  expect(weekLabel('2026-10-05')).toBe('Wk 41')
})

test('labels for days and months', () => {
  expect(monthLabel('2026-09-01')).toBe('Sep 2026')
  expect(dayLabel('2026-10-12')).toBe('12 Oct')
})

test('F20-AC-03: the trend is shown in percentage points, Stable under 2 and a dash without data', () => {
  expect(trendView('up', '12.6')).toEqual({ text: '▲ +12.6 pp', tone: 'up' })
  expect(trendView('down', '-6.5')).toEqual({ text: '▼ −6.5 pp', tone: 'down' })
  expect(trendView('stable', '1.0')).toEqual({ text: 'Stable', tone: 'stable' })
  expect(trendView('none', null)).toEqual({ text: '—', tone: 'none' })
})

test('percent formatting and bar geometry', () => {
  expect(formatPct('87.60')).toBe('87.6%')
  expect(formatPct('94.4', 0)).toBe('94%')
  expect(formatPct(null)).toBe('–')
  expect(markerPercent(350, 700)).toBe(50)
  expect(markerPercent(900, 700)).toBe(100)
  expect(markerPercent(10, 0)).toBe(0)
  expect(fillPercent(318, 700)).toBeCloseTo(45.43, 1)
  expect(fillPercent(800, 700)).toBe(100)
  expect(fillPercent(1, 0)).toBe(0)
})

test('only the six tabs are valid', () => {
  expect(isTab('late')).toBe(true)
  expect(isTab('nope')).toBe(false)
  expect(isTab(null)).toBe(false)
})
