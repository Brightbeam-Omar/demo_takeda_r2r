import { expect, test } from 'vitest'
import {
  formatAge,
  formatClock,
  formatDate,
  formatFeedAge,
  formatTopBarClock,
  freshnessTone,
  minutesBetween,
} from './format'

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

test('F15-FR-03: the top bar clock is dd/mm/yyyy HH:MM in the site timezone', () => {
  expect(formatTopBarClock('2026-10-12T07:00:00Z', 'Europe/Dublin')).toBe('12/10/2026 08:00')
})

test('F15-FR-03 / OQ-080: the feed age reads minutes under 60 and floored hours from 60', () => {
  expect(formatFeedAge(59)).toBe('59 min')
  expect(formatFeedAge(60)).toBe('1 h')
  expect(formatFeedAge(1830)).toBe('30 h')
})

import { formatSiteDateTime, withSiteTimes } from './format'

test('F14-FR-10: an ISO date-time shows as day, month, year and 24-hour time in the site timezone', () => {
  expect(formatSiteDateTime('2026-10-11T01:00:00Z', 'Europe/Dublin')).toBe('11 Oct 2026 02:00')
  expect(formatSiteDateTime('2026-12-03T09:30:00Z', 'Europe/Dublin')).toBe('3 Dec 2026 09:30')
  expect(formatSiteDateTime('2026-10-11T01:00:00', 'UTC')).toBe('11 Oct 2026 01:00')
})

test('F14-FR-10: ISO date-times inside text are replaced, plain dates and other text are left alone', () => {
  const text = 'Approved at 2026-10-08T13:00:00Z. Needed by 2026-10-12; seen 2026-10-09T09:00:00.000+00:00 too.'
  expect(withSiteTimes(text, 'Europe/Dublin')).toBe('Approved at 8 Oct 2026 14:00. Needed by 2026-10-12; seen 9 Oct 2026 10:00 too.')
  expect(withSiteTimes('none', 'UTC')).toBe('none')
})
