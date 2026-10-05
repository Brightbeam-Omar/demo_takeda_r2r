import { expect, test } from 'vitest'
import { formatAge, formatClock, formatDate, freshnessTone, minutesBetween } from './format'

test('F10-FR-03: dates and the demo clock use the 05 copy formats', () => {
  expect(formatDate('2026-10-12')).toBe('12 Oct 2026')
  expect(formatDate(null)).toBe('–')
  expect(formatClock('2026-10-12T07:00:00Z', 'Europe/Dublin')).toBe('Mon 12 Oct 2026 08:00')
})

test('F10-FR-03: freshness colour boundaries are 6 h and 12 h in demo time', () => {
  expect(freshnessTone(359)).toBe('green')
  expect(freshnessTone(360)).toBe('amber')
  expect(freshnessTone(720)).toBe('amber')
  expect(freshnessTone(721)).toBe('red')
  expect(minutesBetween('2026-10-12T07:00:00Z', '2026-10-12T07:12:30Z')).toBe(12)
  expect(formatAge(12)).toBe('12 min')
  expect(formatAge(180)).toBe('3 h')
})
