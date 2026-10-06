import { expect, test } from 'vitest'
import type { RowDetail } from '../api/queries'
import { lotList, milestones, timeline, timelineCsv, totalDays } from './history'

const SLAS = [
  { stage_key: 'receipt', sla_days: 10 },
  { stage_key: 'sampling', sla_days: 5 },
  { stage_key: 'qc_testing', sla_days: 27 },
  { stage_key: 'qa_release', sla_days: 3 },
]

function detailOf(facts: Record<string, unknown>, extra: Record<string, unknown> = {}): RowDetail {
  return {
    row_key: 'RM1|B4410|795',
    stage_key: 'sampling',
    lot_type: '09',
    inspection_lot_no: '795',
    ud_date: null,
    flags: { released: false, offsite: false },
    siblings: [],
    facts: { applicable_sla_json: SLAS, cycle_start_date: '2026-10-08', received_location_type: 'onsite', ...facts },
    ...extra,
  } as unknown as RowDetail
}

test('F19-FR-01: total days run from the cycle start against the sum of the applicable SLAs', () => {
  expect(totalDays(detailOf({}), '2026-10-12')).toEqual({ days: 4, target: 45, over: false })
  expect(totalDays(detailOf({}), '2026-12-01')).toEqual({ days: 54, target: 45, over: true })
})

test('F19-FR-01: a released lot stops counting at its usage decision, and a pending one has no total', () => {
  const released = detailOf({}, { ud_date: '2026-10-20', flags: { released: true, offsite: false } })
  expect(totalDays(released, '2026-12-01')).toEqual({ days: 12, target: 45, over: false })
  expect(totalDays(detailOf({ cycle_start_date: null }), '2026-10-12')).toBeNull()
})

test('F19-FR-01: milestones show the gap from the nearest earlier dated milestone and (pending) for the rest', () => {
  const rows = milestones(detailOf({ gr_date: '2026-01-05', sampling_exit: '2026-10-12' }))
  expect(rows.map((row) => [row.label, row.state, row.date])).toEqual([
    ['Goods Receipt', 'dated', '2026-01-05'],
    ['Call-Off Target', 'na', null],
    ['First Sampled', 'dated', '2026-10-12'],
    ['Sample Shipped', 'na', null],
    ['Usage Decision', 'pending', null],
  ])
  expect(rows[0]?.gap).toBeNull()
  expect(rows[2]?.gap).toEqual({ days: 280, from: 'Goods Receipt' })
})

test('F19-FR-01: a 3PL initial lot has a call-off target (cycle start + receipt SLA) and an offsite lot a shipped date', () => {
  const rows = milestones(
    detailOf(
      { gr_date: '2026-10-01', cycle_start_date: '2026-10-01', received_location_type: '3pl', sample_shipped_date: null },
      { lot_type: '01', flags: { released: false, offsite: true } },
    ),
  )
  expect(rows[1]).toMatchObject({ label: 'Call-Off Target', state: 'dated', date: '2026-10-11', gap: { days: 10, from: 'Goods Receipt' } })
  expect(rows[2]).toMatchObject({ label: 'First Sampled', state: 'pending' })
  expect(rows[3]).toMatchObject({ label: 'Sample Shipped', state: 'pending' })
})

test('F19-FR-01: the timeline has one entry per stage reached; green within the SLA, red over it, blue for the current stage', () => {
  const entries = timeline(
    detailOf(
      {
        receipt_entry: '2026-10-01',
        receipt_exit: '2026-10-14',
        sampling_entry: '2026-10-14',
        sampling_exit: '2026-10-16',
        qc_testing_entry: '2026-10-16',
        qc_testing_exit: null,
        qa_release_entry: null,
      },
      { stage_key: 'qc_testing' },
    ),
    '2026-10-20',
  )
  expect(entries.map((e) => [e.stage_key, e.tone, e.days, e.sla, e.overBy])).toEqual([
    ['receipt', 'red', 13, 10, 3],
    ['sampling', 'green', 2, 5, 0],
    ['qc_testing', 'blue', 4, 27, 0],
  ])
  expect(entries[2]?.exited).toBeNull()
})

test('F19-FR-01: a stage entered and left on the same day shows 0d', () => {
  const [entry] = timeline(detailOf({ receipt_entry: '2026-10-08', receipt_exit: '2026-10-08' }, { stage_key: 'qc_testing' }), '2026-10-12')
  expect(entry).toMatchObject({ days: 0, tone: 'green' })
})

test('F19-FR-01: other lots are listed oldest first with the current lot marked', () => {
  const lot = (n: number, type: string) => ({ row_key: `RM1|B4410|${n}`, lot_type: type, inspection_lot_no: String(n), stage_key: 'released' })
  const detail = detailOf({}, { siblings: [lot(430, '09'), lot(22, '01'), lot(195, '09'), lot(105, '09')] })
  const lots = lotList(detail)
  expect(lots.map((l) => [l.label, l.current])).toEqual([
    ['Initial', false],
    ['Re-eval 1', false],
    ['Re-eval 2', false],
    ['Re-eval 3', false],
    ['Re-eval 4', true],
  ])
  expect(lots[0]?.rowKey).toBe('RM1|B4410|22')
})

test('F19-FR-01: the timeline export is a CSV with the stage, dates, SLA, days and whether it was within the SLA', () => {
  const entries = timeline(detailOf({ receipt_entry: '2026-10-01', receipt_exit: '2026-10-14' }, { stage_key: 'qc_testing' }), '2026-10-20')
  expect(timelineCsv(entries, (key) => key.toUpperCase())).toBe(
    'Stage,Entered,Exited,SLA days,Days,Within SLA\nRECEIPT,2026-10-01,2026-10-14,10,13,no\n',
  )
})
