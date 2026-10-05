import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { RowDetail } from '../../api/queries'
import { QualitySection } from './Sections'
import { SiblingLots, StageTimeline } from './Timeline'

const lot = (n: number, type: string, stage = 'released') =>
  ({ row_key: `RM1|B4410|${n}`, lot_type: type, inspection_lot_no: String(n), stage_key: stage }) as never

function detailOf(extra: Record<string, unknown>): RowDetail {
  return {
    row_key: 'RM1|B4410|795',
    stage_key: 'sampling',
    plan: { effective_slas: { receipt: 10, sampling: 4 } },
    siblings: [],
    deviations: [],
    facts: {},
    ...extra,
  } as unknown as RowDetail
}

test('F11-AC-03: B4410 lists the initial lot, three earlier re-evals and the current one, oldest first', async () => {
  const detail = detailOf({
    row_key: 'RM1|B4410|795',
    lot_type: '09',
    inspection_lot_no: '795',
    stage_key: 'sampling',
    siblings: [lot(430, '09'), lot(22, '01'), lot(195, '09'), lot(105, '09')],
  })
  const open = vi.fn()
  render(<SiblingLots detail={detail} stageLabel={(k) => k} onOpen={open} />)
  const items = screen.getAllByTestId('lot-item')
  expect(items).toHaveLength(5)
  expect(items.map((item) => item.textContent)).toEqual([
    expect.stringContaining('Initial'),
    expect.stringContaining('Re-eval 1'),
    expect.stringContaining('Re-eval 2'),
    expect.stringContaining('Re-eval 3'),
    expect.stringContaining('Re-eval 4'),
  ])
  expect(within(items[4]).getByRole('button')).toBeDisabled() // the current lot
  await userEvent.click(within(items[0]).getByRole('button'))
  expect(open).toHaveBeenCalledWith('RM1|B4410|22')
})

test('F11-FR-01: the timeline shows days per stage against the SLA, the compressed SLA and in-progress stages', () => {
  const detail = detailOf({
    facts: {
      applicable_sla_json: [
        { stage_key: 'receipt', sla_days: 10 },
        { stage_key: 'sampling', sla_days: 7 },
      ],
      receipt_entry: '2026-09-01',
      receipt_exit: '2026-09-14',
      sampling_entry: '2026-09-14',
      sampling_exit: null,
    },
  })
  render(<StageTimeline detail={detail} today="2026-09-20" stageLabel={(k) => k} />)
  const rows = within(screen.getByTestId('stage-timeline')).getAllByRole('row').slice(1)
  expect(rows[0]).toHaveTextContent('receipt1 Sep14 Sep13 d10 d') // 13 days against a 10 day SLA
  expect(rows[0].children[3]).toHaveClass('text-red-700')
  expect(rows[1]).toHaveTextContent('in progress6 d7 d → 4 d')
})

test('F11-AC-06: the quality section shows an open major deviation and a red light', () => {
  const detail = detailOf({
    deviation_light: 'red',
    inbound_light: 'green',
    deviations: [{ deviation_no: 'DEV-000123', title: 'Seal damaged', severity: 'major', status: 'open', opened_on: '2026-10-01', owner: 'QA' }],
    facts: { inbound_check_status: 'passed', inbound_check_completed_date: '2026-09-02' },
  })
  render(<QualitySection detail={detail} />)
  expect(screen.getByRole('img', { name: 'Deviations: red' })).toBeInTheDocument()
  expect(screen.getByTestId('deviation-list')).toHaveTextContent('DEV-000123 Seal damagedMajor · Open')
  expect(screen.getByText(/Inbound check: Passed on 2 Sep 2026/)).toBeInTheDocument()
})
