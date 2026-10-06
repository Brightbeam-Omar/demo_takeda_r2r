import type { Schemas } from '../api/client'

export type TabKey = 'summary' | 'sla' | 'trends' | 'late' | 'release-rate' | 'adherence'

export const TABS: { key: TabKey; label: string; usesYear: boolean }[] = [
  { key: 'summary', label: 'Executive Summary', usesYear: true },
  { key: 'sla', label: 'SLA Performance', usesYear: false },
  { key: 'trends', label: 'Trends', usesYear: false },
  { key: 'late', label: 'Late Items', usesYear: false },
  { key: 'release-rate', label: 'Release Rate', usesYear: true },
  { key: 'adherence', label: 'Adherence to NBD', usesYear: true },
]

export type Summary = Schemas['SummaryOut']
export type SlaReport = Schemas['SlaOut']
export type TrendsReport = Schemas['TrendsOut']
export type LateReport = Schemas['LateOut']
export type ReleaseRateReport = Schemas['ReleaseRateOut']
export type AdherenceReport = Schemas['AdherenceOut']

export const isTab = (value: string | null): value is TabKey => TABS.some((tab) => tab.key === value)

/** `87.6` → `87.6%`, one decimal; a missing value is a dash (05 Copy). */
export function formatPct(value: string | number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '–'
  return `${Number(value).toFixed(digits)}%`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** The ISO 8601 week number of a calendar date (the week of its Thursday). */
export function isoWeek(iso: string): number {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  const date = new Date(Date.UTC(year!, month! - 1, day))
  const weekday = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() + 4 - weekday)
  const yearStart = Date.UTC(date.getUTCFullYear(), 0, 1)
  return Math.ceil(((date.getTime() - yearStart) / 86_400_000 + 1) / 7)
}

/** `2026-10-05` → `Wk 41`. */
export const weekLabel = (iso: string): string => `Wk ${isoWeek(iso)}`

/** `2026-09-01` → `Sep 2026`. */
export function monthLabel(iso: string): string {
  const [year, month] = iso.slice(0, 10).split('-').map(Number)
  return `${MONTHS[month! - 1]} ${year}`
}

/** `2026-10-12` → `12 Oct`. */
export function dayLabel(iso: string): string {
  const [, month, day] = iso.slice(0, 10).split('-').map(Number)
  return `${day} ${MONTHS[month! - 1]}`
}

export interface TrendView {
  text: string
  tone: 'up' | 'down' | 'stable' | 'none'
}

/** ▲ +12.6 pp (green), ▼ −4.0 pp (red), Stable, or a dash (OQ-126). */
export function trendView(direction: string, delta: string | number | null): TrendView {
  if (direction === 'stable') return { text: 'Stable', tone: 'stable' }
  if (delta === null || (direction !== 'up' && direction !== 'down')) return { text: '—', tone: 'none' }
  const value = Math.abs(Number(delta)).toFixed(1)
  return direction === 'up'
    ? { text: `▲ +${value} pp`, tone: 'up' }
    : { text: `▼ −${value} pp`, tone: 'down' }
}

/** Where the target marker sits on a bar that runs from 0 to the annual target, as a percentage of the bar. */
export function markerPercent(prorata: number, annual: number): number {
  return annual <= 0 ? 0 : Math.min(100, (prorata / annual) * 100)
}

/** The width of a progress bar fill, never past the bar. */
export function fillPercent(value: number, whole: number): number {
  return whole <= 0 ? 0 : Math.max(0, Math.min(100, (value / whole) * 100))
}
