import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Overview, Reference } from '../../api/queries'
import { FlowStrip } from './FlowStrip'
import { renderWithProviders } from '../../test-utils'

const entries = [
  { stage_key: 'receipt', label: 'Receipt', count: 39, breached: true, late_count: 5 },
  { stage_key: 'qc_testing', label: 'QC Testing', count: 120, breached: false, late_count: 0 },
  { stage_key: 'released', label: 'Released', count: 300, breached: false, late_count: 0 },
]
const stages = [
  { stage_key: 'receipt', sla_days: 10 },
  { stage_key: 'qc_testing', sla_days: 42 },
  { stage_key: 'released', sla_days: 0, terminal: true },
] as unknown as Reference['stages']

function setup(mode: Overview['mode'], onToggleStage = vi.fn()) {
  renderWithProviders(
    <FlowStrip entries={entries} stages={stages} mode={mode} onHoldCount={7} activeStage={null} onHoldActive={false} onToggleStage={onToggleStage} onToggleHold={vi.fn()} />,
  )
  return onToggleStage
}

test('F10-AC-07: the flow strip shows counts, SLA days, a small late count and the open-pipeline total', () => {
  setup('snapshot')
  expect(screen.getByText('Open pipeline')).toBeInTheDocument()
  expect(screen.getByTestId('flow-total')).toHaveTextContent('159') // 39 + 120, released excluded
  expect(screen.getByTestId('late-receipt')).toHaveTextContent('5 late')
  expect(screen.queryByTestId('late-qc_testing')).not.toBeInTheDocument()
  expect(screen.getByTestId('flow-receipt')).not.toHaveClass('border-red-500')
  expect(screen.getByTestId('flow-qc_testing')).toHaveTextContent('SLA 42 d')
  expect(screen.getByTestId('flow-on_hold')).toHaveTextContent('7')
})

test('F10-FR-07: the caption follows the mode and a click toggles the stage', async () => {
  const toggle = setup('due_in_period')
  expect(screen.getByTestId('flow-caption')).toHaveTextContent('due in period')
  await userEvent.click(screen.getByTestId('flow-qc_testing'))
  expect(toggle).toHaveBeenCalledWith('qc_testing')
})

test('F10-FR-07: the outline marks only the selected stage', () => {
  renderWithProviders(
    <FlowStrip entries={entries} stages={stages} mode="snapshot" onHoldCount={0} activeStage="receipt" onHoldActive={false} onToggleStage={vi.fn()} onToggleHold={vi.fn()} />,
  )
  expect(screen.getByTestId('flow-receipt')).toHaveClass('ring-2')
  expect(screen.getByTestId('flow-qc_testing')).not.toHaveClass('ring-2')
})
