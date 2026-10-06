import type { RowDetail } from '../api/queries'
import { daysBetween } from './format'

/** Pure functions behind the drawer's history sections (F19-FR-01): everything derives from published facts. */

interface Sla {
  stage_key: string
  sla_days: number
}

type Facts = Record<string, unknown>

const factsOf = (detail: RowDetail) => detail.facts as Facts
const slasOf = (detail: RowDetail) => (factsOf(detail).applicable_sla_json ?? []) as Sla[]
const dateOf = (value: unknown): string | null => (typeof value === 'string' && value ? value : null)

function addDays(iso: string, days: number): string {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number) as [number, number, number]
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

export interface TotalDays {
  days: number
  /** The sum of the applicable SLAs of the lot. */
  target: number
  over: boolean
}

/** Today minus the cycle start (a released lot stops at its usage decision), against the sum of the SLAs. */
export function totalDays(detail: RowDetail, today: string): TotalDays | null {
  const start = dateOf(factsOf(detail).cycle_start_date)
  if (!start) return null
  const end = detail.flags.released && detail.ud_date ? detail.ud_date : today
  const days = daysBetween(start, end)
  const target = slasOf(detail).reduce((sum, sla) => sum + sla.sla_days, 0)
  return { days, target, over: days > target }
}

export interface Milestone {
  label: string
  /** `dated` has a date, `pending` is expected but missing, `na` does not apply to this lot. */
  state: 'dated' | 'pending' | 'na'
  date: string | null
  /** `+Nd from <previous>`: from the nearest earlier dated milestone. */
  gap: { days: number; from: string } | null
}

export function milestones(detail: RowDetail): Milestone[] {
  const facts = factsOf(detail)
  const start = dateOf(facts.cycle_start_date)
  const receiptSla = slasOf(detail).find((sla) => sla.stage_key === 'receipt')?.sla_days ?? 0
  const threepl = detail.lot_type === '01' && facts.received_location_type === '3pl'
  const draft: [string, 'dated' | 'pending' | 'na', string | null][] = [
    ['Goods Receipt', dateOf(facts.gr_date) ? 'dated' : 'pending', dateOf(facts.gr_date)],
    ['Call-Off Target', threepl && start ? 'dated' : 'na', threepl && start ? addDays(start, receiptSla) : null],
    ['First Sampled', dateOf(facts.sampling_exit) ? 'dated' : 'pending', dateOf(facts.sampling_exit)],
    [
      'Sample Shipped',
      !detail.flags.offsite ? 'na' : dateOf(facts.sample_shipped_date) ? 'dated' : 'pending',
      detail.flags.offsite ? dateOf(facts.sample_shipped_date) : null,
    ],
    ['Usage Decision', detail.ud_date ? 'dated' : 'pending', detail.ud_date],
  ]
  const out: Milestone[] = []
  let previous: { label: string; date: string } | null = null
  for (const [label, state, date] of draft) {
    const gap = state === 'dated' && date && previous ? { days: daysBetween(previous.date, date), from: previous.label } : null
    out.push({ label, state, date, gap })
    if (state === 'dated' && date) previous = { label, date }
  }
  return out
}

export interface TimelineEntry {
  stage_key: string
  entered: string
  exited: string | null
  sla: number
  days: number
  /** Days over the SLA, 0 when within it. */
  overBy: number
  /** Green within the SLA, red over it, blue for the stage the lot is in now. */
  tone: 'green' | 'red' | 'blue'
}

/** One entry per stage the lot has reached, in the order of its applicable SLAs. */
export function timeline(detail: RowDetail, today: string): TimelineEntry[] {
  const facts = factsOf(detail)
  const entries: TimelineEntry[] = []
  for (const { stage_key, sla_days } of slasOf(detail)) {
    const entered = dateOf(facts[`${stage_key}_entry`])
    if (!entered) continue
    const exited = dateOf(facts[`${stage_key}_exit`])
    const days = daysBetween(entered, exited ?? today)
    const overBy = Math.max(0, days - sla_days)
    const current = !exited && detail.stage_key === stage_key
    entries.push({ stage_key, entered, exited, sla: sla_days, days, overBy, tone: current ? 'blue' : overBy > 0 ? 'red' : 'green' })
  }
  return entries
}

export interface LotItem {
  rowKey: string
  label: string
  lotNo: string
  stageKey: string
  current: boolean
}

type LotLike = { row_key: string; lot_type: string; inspection_lot_no: string; stage_key: string }

/** Every lot of the batch, oldest first: the initial lot, then the re-evaluations; the open one is marked. */
export function lotList(detail: RowDetail): LotItem[] {
  const all = [detail as unknown as LotLike, ...(detail.siblings as unknown as LotLike[])].sort(
    (a, b) => (a.lot_type === '01' ? 0 : 1) - (b.lot_type === '01' ? 0 : 1) || a.inspection_lot_no.localeCompare(b.inspection_lot_no, undefined, { numeric: true }),
  )
  let reeval = 0
  return all.map((lot) => ({
    rowKey: lot.row_key,
    label: lot.lot_type === '01' ? 'Initial' : `Re-eval ${++reeval}`,
    lotNo: lot.inspection_lot_no,
    stageKey: lot.stage_key,
    current: lot.row_key === detail.row_key,
  }))
}

/** The timeline as CSV for the Export button (built here, no endpoint: OQ-113). */
export function timelineCsv(entries: TimelineEntry[], stageLabel: (key: string) => string): string {
  const cell = (value: string | number) => (/[",\n]/.test(String(value)) ? `"${String(value).replace(/"/g, '""')}"` : String(value))
  const lines = ['Stage,Entered,Exited,SLA days,Days,Within SLA']
  for (const e of entries) {
    lines.push([stageLabel(e.stage_key), e.entered, e.exited ?? '', e.sla, e.days, e.overBy === 0 ? 'yes' : 'no'].map(cell).join(','))
  }
  return `${lines.join('\n')}\n`
}
