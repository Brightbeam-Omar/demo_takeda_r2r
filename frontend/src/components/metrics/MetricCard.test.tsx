import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { Metrics } from '../../api/queries'
import { MetricCard } from './MetricCard'
import { MetricsRibbon, metricsTitle, weekLabel } from './MetricsRibbon'
import { renderWithProviders } from '../../test-utils'

type Metric = Metrics['metrics'][number]

const active = (id: string, pct: string, rag: string, onTime = 17, completed = 18) =>
  ({
    metric_id: id,
    label: 'Sampling On-Time',
    stage_key: 'sampling',
    sla_days: 7,
    computed_in: 'pipeline',
    status: 'active',
    null_reason: null,
    weeks: [
      { week_start: '2026-09-28', completed: 12, on_time: 9, pct: '75.0', rag: 'red' },
      { week_start: '2026-10-05', completed, on_time: onTime, pct, rag },
      { week_start: '2026-10-12', completed: 0, on_time: 0, pct: null, rag: null },
    ],
  }) as unknown as Metric

const waiting = {
  metric_id: 'M1', label: 'Receipt On-Time', stage_key: 'receipt', sla_days: 10, computed_in: 'app', status: 'awaiting_signal',
  null_reason: 'Physical receipt date comes from the 3PL feed, enabled in Tier 2', weeks: [],
} as unknown as Metric

test('F17-AC-04: the card reads METRIC n, name, big %, SLA and on_time/completed', () => {
  renderWithProviders(<MetricCard metric={active('M3', '94.4', 'green')} stageLabel="Sampling" />)
  const card = screen.getByTestId('metric-M3')
  expect(card).toHaveTextContent('Metric 3')
  expect(card).toHaveTextContent('Sampling On-Time')
  expect(screen.getByTestId('metric-headline')).toHaveTextContent('94%')
  expect(screen.getByTestId('metric-counts')).toHaveTextContent('SLA 7d · 17/18')
  expect(screen.getByTestId('metric-wtd')).toHaveTextContent('WTD –')
  expect(screen.getByTestId('sparkline')).toBeInTheDocument()
})

test('F17-FR-06: the 4 px top bar is green at or above the green threshold, amber, red, and absent for N/A', () => {
  const { unmount } = renderWithProviders(<MetricCard metric={active('M3', '94.4', 'green')} />)
  expect(screen.getByTestId('metric-bar')).toHaveClass('bg-rag-green', 'h-1')
  unmount()
  const amber = renderWithProviders(<MetricCard metric={active('M6', '83.7', 'amber')} />)
  expect(screen.getByTestId('metric-bar')).toHaveClass('bg-rag-amber')
  amber.unmount()
  const red = renderWithProviders(<MetricCard metric={active('M7', '69.2', 'red')} />)
  expect(screen.getByTestId('metric-bar')).toHaveClass('bg-rag-red')
  red.unmount()
  renderWithProviders(<MetricCard metric={waiting} />)
  expect(screen.queryByTestId('metric-bar')).not.toBeInTheDocument()
})

test('F17-FR-06: an N/A card reads N/A with the null_reason in the ⓘ tooltip', () => {
  renderWithProviders(<MetricCard metric={waiting} />)
  expect(screen.getByTestId('metric-headline')).toHaveTextContent('N/A')
  expect(screen.getByTestId('metric-info')).toHaveAttribute('title', 'Receipt On-Time: Physical receipt date comes from the 3PL feed, enabled in Tier 2')
})

test('F17-FR-06: the ⓘ tooltip says how it is computed and names the source view; the % opens the explanation', () => {
  renderWithProviders(<MetricCard metric={active('M3', '94.4', 'green')} stageLabel="Sampling" />)
  expect(screen.getByTestId('metric-info').getAttribute('title')).toMatch(/within the SLA .*Source: weekly_metrics_v/)
  expect(screen.getByRole('button', { name: 'Explain M3' })).toHaveTextContent('94%')
})

test('F17-AC-04: the header reads Week 41 (2026) — 7 R2R Metrics from the published week_start, ISO week-year', () => {
  const metrics = [waiting, active('M3', '94.4', 'green')]
  expect(weekLabel(metrics)).toBe('Week 41 (2026)')
  expect(metricsTitle([...metrics, ...Array.from({ length: 5 }, (_, i) => ({ ...waiting, metric_id: `M${i + 4}` }))])).toBe('Week 41 (2026) — 7 R2R Metrics')
  const boundary = active('M3', '90', 'green')
  boundary.weeks = [{ week_start: '2024-12-30', completed: 1, on_time: 1, pct: '100', rag: 'green' }, boundary.weeks[2]!]
  expect(weekLabel([boundary])).toBe('Week 1 (2025)')
})

test('F17-FR-06: the ribbon renders one card per metric (seven)', () => {
  const metrics = Array.from({ length: 7 }, (_, i) => ({ ...waiting, metric_id: `M${i + 1}` })) as unknown as Metric[]
  renderWithProviders(<MetricsRibbon metrics={metrics} />)
  expect(screen.getAllByTestId(/^metric-M\d$/)).toHaveLength(7)
})
