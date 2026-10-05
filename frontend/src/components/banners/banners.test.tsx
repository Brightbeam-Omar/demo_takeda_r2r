import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { DEFAULT_TERMS, TermsContext } from '../../hooks/useTerms'
import { AdjustedBanner } from './AdjustedBanner'
import { InsightsBanner } from './InsightsBanner'

test('F16-FR-06: the adjusted banner counts, uses the singular for one and opens the window', async () => {
  const onView = vi.fn()
  const { rerender } = render(<AdjustedBanner count={3} onView={onView} />)
  expect(screen.getByTestId('adjusted-banner')).toHaveTextContent('3 adjusted needs-by dates (planner overrides, across all stages)')
  await userEvent.click(screen.getByRole('button', { name: 'View details' }))
  expect(onView).toHaveBeenCalledOnce()
  rerender(<AdjustedBanner count={1} onView={onView} />)
  expect(screen.getByTestId('adjusted-banner')).toHaveTextContent('1 adjusted needs-by date (')
  expect(screen.getByTestId('adjusted-banner')).not.toHaveTextContent('dates')
})

test('F16-FR-06: the adjusted banner is blue (info) with a count too; only Insights turns red; the icon is an SVG, not an emoji', () => {
  render(<AdjustedBanner count={3} onView={vi.fn()} />)
  const banner = screen.getByTestId('adjusted-banner')
  expect(banner.className).toContain('bg-blue-50')
  expect(banner.className).not.toMatch(/amber|red/)
  expect(banner.querySelector('svg')).not.toBeNull()
  expect(banner.textContent).not.toContain('📅')
})

test('F16-FR-06 / AC-06: with none the adjusted banner is the blue empty state with no button', () => {
  render(<AdjustedBanner count={0} onView={vi.fn()} />)
  const banner = screen.getByTestId('adjusted-banner')
  expect(banner).toHaveTextContent('No adjusted needs-by dates in this period')
  expect(banner.className).toContain('bg-blue-50')
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test('F16-FR-06: the planner-overrides wording is profile vocabulary', () => {
  render(
    <TermsContext.Provider value={{ ...DEFAULT_TERMS, planner_overrides: 'schedule overrides' }}>
      <AdjustedBanner count={2} onView={vi.fn()} />
    </TermsContext.Provider>,
  )
  expect(screen.getByTestId('adjusted-banner')).toHaveTextContent('(schedule overrides, across all stages)')
})

test('F16-FR-08: the insights banner is red with View all N → when there are batches', async () => {
  const onView = vi.fn()
  render(<InsightsBanner count={4} onView={onView} />)
  const banner = screen.getByTestId('insights-banner')
  expect(banner).toHaveTextContent('LIMS–ERP Insights (4 batches)')
  expect(banner.className).toContain('bg-red-50')
  await userEvent.click(screen.getByRole('button', { name: 'View all 4 →' }))
  expect(onView).toHaveBeenCalledOnce()
})

test('F16-FR-08 / AC-06: with none the insights banner is blue with the empty text, using the profile term', () => {
  render(
    <TermsContext.Provider value={{ ...DEFAULT_TERMS, insights_banner: 'Source Insights' }}>
      <InsightsBanner count={0} onView={vi.fn()} />
    </TermsContext.Provider>,
  )
  const banner = screen.getByTestId('insights-banner')
  expect(banner).toHaveTextContent('No Source Insights in this period')
  expect(banner.className).toContain('bg-blue-50')
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})
