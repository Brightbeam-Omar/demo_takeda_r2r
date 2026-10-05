const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** `2026-10-12` → `12 Oct 2026` (05 Copy). Dates are site-local calendar dates, so no timezone maths. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '–'
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  return `${day} ${MONTHS[month - 1]} ${year}`
}

/** `2026-10-12` → `12 Oct` for compact cells. */
export function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return '–'
  const [, month, day] = iso.slice(0, 10).split('-').map(Number)
  return `${day} ${MONTHS[month - 1]}`
}

/** The demo clock as shown in the top bar: `Mon 12 Oct 2026 08:00`, in the site timezone. */
export function formatClock(nowUtc: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(nowUtc))
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return `${get('weekday')} ${get('day')} ${get('month')} ${get('year')} ${get('hour')}:${get('minute')}`
}

/** Minutes between two instants (the demo clock minus the last successful run), never negative. */
export function minutesBetween(fromIso: string, toIso: string): number {
  return Math.max(0, Math.floor((new Date(toIso).getTime() - new Date(fromIso).getTime()) / 60_000))
}

/** `12 min`, `3 h`, `2 d`. */
export function formatAge(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  if (minutes < 60 * 48) return `${Math.floor(minutes / 60)} h`
  return `${Math.floor(minutes / 1440)} d`
}

export type FreshnessTone = 'green' | 'amber' | 'red'

/** Green under 6 h, amber 6–12 h, red over 12 h, measured in demo time (05 Layout). */
export function freshnessTone(minutes: number): FreshnessTone {
  if (minutes < 6 * 60) return 'green'
  return minutes <= 12 * 60 ? 'amber' : 'red'
}

/** `small_molecule` → `Small molecule`. */
export function humanize(value: string): string {
  const text = value.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Whole days from one calendar date to another (`2026-10-05` → `2026-10-12` is 7). */
export function daysBetween(fromIso: string, toIso: string): number {
  const [fy, fm, fd] = fromIso.slice(0, 10).split('-').map(Number)
  const [ty, tm, td] = toIso.slice(0, 10).split('-').map(Number)
  return Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(fy, fm - 1, fd)) / 86_400_000)
}

/** `just now`, `12 s ago`, `2 min ago`, `3 h ago`, `2 d ago`. Sync times are wall-clock, so they are never shown as dates. */
export function formatRelative(seconds: number): string {
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds} s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} h ago`
  return `${Math.floor(seconds / 86_400)} d ago`
}

/** `850 ms`, `1.4 s`, `2 min 5 s`. */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '–'
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`
}
