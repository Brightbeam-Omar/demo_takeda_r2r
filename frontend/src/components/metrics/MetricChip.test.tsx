import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { Metrics } from '../../api/queries'
import { MetricChip } from './MetricChip'

type Metric = Metrics['metrics'][number]

const active = {
  metric_id: 'M3',
  label: 'Sampling On-Time',
  stage_key: 'sampling',
  sla_days: 7,
  computed_in: 'pipeline',
  status: 'active',
  null_reason: null,
  weeks: [
    { week_start: '2026-09-28', completed: 18, on_time: 17, pct: '94.4', rag: 'green' },
    { week_start: '2026-10-05', completed: 10, on_time: 9, pct: '85.0', rag: 'amber' },
    { week_start: '2026-10-12', completed: 0, on_time: 0, pct: null, rag: null },
  ],
} as unknown as Metric

test('F10-AC-07: the headline is the last complete week, week to date is secondary, with a sparkline', () => {
  render(<MetricChip metric={active} />)
  expect(screen.getByTestId('metric-headline')).toHaveTextContent('85%')
  expect(screen.getByTestId('metric-wtd')).toHaveTextContent('WTD –')
  expect(screen.getByTestId('metric-M3')).toHaveClass('border-amber-200')
  expect(screen.getByTestId('sparkline')).toBeInTheDocument()
  expect(screen.getByText('SLA 7 d')).toBeInTheDocument()
})

test('F10-AC-06: an awaiting-signal metric shows "–" with the reason as tooltip and a Tier 2 tag', () => {
  const waiting = { ...active, metric_id: 'M1', status: 'awaiting_signal', weeks: [], null_reason: 'Comes from the 3PL feed' } as unknown as Metric
  render(<MetricChip metric={waiting} />)
  expect(screen.getByTestId('metric-M1')).toHaveAttribute('title', 'Comes from the 3PL feed')
  expect(screen.getByText('–')).toBeInTheDocument()
  expect(screen.getByText('Tier 2')).toBeInTheDocument()
})
