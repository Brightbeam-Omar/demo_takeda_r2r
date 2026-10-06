import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Overview, Reference } from '../../api/queries'
import { StageStrip, activeTotal, skipNoun } from './StageStrip'
import { renderWithProviders } from '../../test-utils'

const entries = [
  { stage_key: 'pending', label: 'Pending', count: 14, breached: false, late_count: 0, skip_count: null },
  { stage_key: 'receipt', label: 'Receipt', count: 39, breached: true, late_count: 5, skip_count: null },
  { stage_key: 'call_off', label: 'Call Off', count: 58, breached: false, late_count: 2, skip_count: 31 },
  { stage_key: 'qc_testing', label: 'QCL Testing', count: 120, breached: false, late_count: 0, skip_count: null },
  { stage_key: 'released', label: 'Released', count: 300, breached: false, late_count: 0, skip_count: null },
]
const stages = [
  { stage_key: 'pending', sla_days: 0, show_card: false },
  { stage_key: 'receipt', sla_days: 10, show_card: true },
  { stage_key: 'call_off', sla_days: 5, show_card: true },
  { stage_key: 'qc_testing', sla_days: 42, show_card: true },
  { stage_key: 'released', sla_days: 0, terminal: true, show_card: true },
] as unknown as Reference['stages']

function setup(overrides: Partial<Parameters<typeof StageStrip>[0]> = {}, mode: Overview['mode'] = 'snapshot') {
  const handlers = { onToggleStage: vi.fn(), onClearStages: vi.fn(), onToggleHold: vi.fn(), onOpenDeliveries: vi.fn() }
  renderWithProviders(
    <StageStrip
      entries={entries}
      stages={stages}
      mode={mode}
      onHoldCount={7}
      activeStages={[]}
      onHoldActive={false}
      deliveries={23}
      {...handlers}
      {...overrides}
    />,
  )
  return handlers
}

test('F17-FR-04: Expected Delivery, Total Pipeline, the visible stages numbered from 1, then On Hold', () => {
  setup()
  const cards = screen.getAllByRole('button').filter((b) => b.dataset['testid']?.startsWith('flow-'))
  expect(cards.map((card) => card.dataset['testid'])).toEqual([
    'flow-expected-delivery', 'flow-total', 'flow-receipt', 'flow-call_off', 'flow-qc_testing', 'flow-released', 'flow-on_hold',
  ])
  expect(screen.queryByTestId('flow-pending')).not.toBeInTheDocument() // show_card: false, still in the total
  expect(screen.getByTestId('flow-receipt')).toHaveTextContent('Stage 1')
  expect(screen.getByTestId('flow-released')).toHaveTextContent('Stage 4')
  expect(screen.getAllByText('▸')).toHaveLength(4)
  expect(screen.getByTestId('flow-on_hold')).toHaveTextContent('Frozen batches')
})

test('F17-AC-01: Stage 0 shows the open PO lines, dashed, and is not part of the total', async () => {
  const { onOpenDeliveries } = setup()
  expect(screen.getByTestId('expected-delivery-count')).toHaveTextContent('23')
  expect(screen.getByTestId('flow-expected-delivery')).toHaveClass('border-dashed')
  expect(screen.getByTestId('flow-expected-delivery')).toHaveTextContent('Open PO lines')
  expect(screen.getByTestId('flow-total')).toHaveTextContent('231') // 14 + 39 + 58 + 120; released and PO lines excluded
  expect(screen.getByTestId('flow-total')).toHaveTextContent('Active batches')
  await userEvent.click(screen.getByTestId('flow-expected-delivery'))
  expect(onOpenDeliveries).toHaveBeenCalledOnce()
})

test('F17-FR-04: Stage 0 reads "Due this period" when a period is set', () => {
  setup({}, 'due_in_period')
  expect(screen.getByTestId('flow-expected-delivery')).toHaveTextContent('Due this period')
  expect(screen.getByTestId('flow-caption')).toHaveTextContent('Due in period')
})

test('F17-FR-04: a stage card shows its SLA, a red late count and the green skip note', () => {
  setup()
  expect(screen.getByTestId('flow-call_off')).toHaveTextContent('SLA 5 d')
  expect(screen.getByTestId('late-call_off')).toHaveTextContent('2 late')
  expect(screen.getByTestId('skip-call_off')).toHaveTextContent('31 skip call-off')
  expect(screen.getByTestId('skip-call_off')).toHaveClass('text-green-700')
  expect(screen.queryByTestId('skip-receipt')).not.toBeInTheDocument()
  expect(screen.queryByTestId('late-released')).not.toBeInTheDocument()
})

test('F17-FR-05: Total Pipeline is selected by default; a stage selection deselects it and a click toggles a stage', async () => {
  const { onToggleStage, onClearStages } = setup({ activeStages: [] })
  expect(screen.getByTestId('flow-total')).toHaveAttribute('aria-pressed', 'true')
  await userEvent.click(screen.getByTestId('flow-qc_testing'))
  expect(onToggleStage).toHaveBeenCalledWith('qc_testing')
  await userEvent.click(screen.getByTestId('flow-total'))
  expect(onClearStages).toHaveBeenCalledOnce()
})

test('F17-FR-05: selected cards get the lavender tint and indigo outline, the rest stay grey, and Total turns off', () => {
  setup({ activeStages: ['receipt', 'qc_testing'] })
  for (const key of ['receipt', 'qc_testing']) {
    expect(screen.getByTestId(`flow-${key}`)).toHaveClass('bg-accent-tint', 'ring-accent')
  }
  expect(screen.getByTestId('flow-call_off')).toHaveClass('bg-panel')
  expect(screen.getByTestId('flow-total')).toHaveAttribute('aria-pressed', 'false')
})

test('F17-AC-02: selecting stages does not change the card counts', () => {
  setup({ activeStages: ['receipt', 'qc_testing'] })
  expect(within(screen.getByTestId('flow-receipt')).getByText('39')).toBeInTheDocument()
  expect(within(screen.getByTestId('flow-call_off')).getByText('58')).toBeInTheDocument()
})

test('F17-FR-04: helpers: the active total leaves released out, and the skip noun is hyphenated', () => {
  expect(activeTotal(entries, stages)).toBe(231)
  expect(skipNoun('Call Off')).toBe('call-off')
  expect(skipNoun('QCL Ship For External Testing')).toBe('QCL-ship')
})
