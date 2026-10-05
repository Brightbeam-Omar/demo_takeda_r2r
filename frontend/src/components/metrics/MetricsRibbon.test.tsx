import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { Metrics } from '../../api/queries'
import { MetricsRibbon } from './MetricsRibbon'

test('F10-FR-08: the ribbon renders one chip per metric (seven)', () => {
  const metrics = Array.from({ length: 7 }, (_, i) => ({
    metric_id: `M${i + 1}`, label: 'x', status: 'awaiting_signal', null_reason: 'r', weeks: [], sla_days: null,
  })) as unknown as Metrics['metrics']
  render(<MetricsRibbon metrics={metrics} />)
  expect(screen.getAllByTestId(/^metric-M\d$/)).toHaveLength(7)
})
