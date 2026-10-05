import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Overview, Reference } from '../../api/queries'
import { FlowStrip } from './FlowStrip'

const entries = [
  { stage_key: 'receipt', label: 'Receipt', count: 39, breached: true },
  { stage_key: 'qc_testing', label: 'QC Testing', count: 120, breached: false },
]
const stages = [
  { stage_key: 'receipt', sla_days: 10 },
  { stage_key: 'qc_testing', sla_days: 42 },
] as unknown as Reference['stages']

function setup(mode: Overview['mode'], onToggleStage = vi.fn()) {
  render(
    <FlowStrip entries={entries} stages={stages} mode={mode} onHoldCount={7} activeStage={null} onHoldActive={false} onToggleStage={onToggleStage} onToggleHold={vi.fn()} />,
  )
  return onToggleStage
}

test('F10-AC-07: the flow strip shows counts, SLA days, a breached outline and the total', () => {
  setup('snapshot')
  expect(screen.getByTestId('flow-total')).toHaveTextContent('159')
  expect(screen.getByTestId('flow-receipt')).toHaveClass('border-red-500')
  expect(screen.getByTestId('flow-qc_testing')).toHaveTextContent('SLA 42 d')
  expect(screen.getByTestId('flow-on_hold')).toHaveTextContent('7')
})

test('F10-FR-07: the caption follows the mode and a click toggles the stage', async () => {
  const toggle = setup('due_in_period')
  expect(screen.getByTestId('flow-caption')).toHaveTextContent('due in period')
  await userEvent.click(screen.getByTestId('flow-qc_testing'))
  expect(toggle).toHaveBeenCalledWith('qc_testing')
})
