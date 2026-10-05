import { expect, test } from '@playwright/test'

test('F10-AC-01: the Overview loads with seeded data in under 2 s and renders every band', async ({ page }) => {
  const errors: string[] = []
  page.on('console', (message) => message.type() === 'error' && errors.push(message.text()))

  const started = Date.now()
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const elapsed = Date.now() - started
  expect(elapsed, `Overview took ${elapsed} ms`).toBeLessThan(2000)

  await expect(page.getByRole('region', { name: 'Filters' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Alerts' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Pipeline by Stage' })).toBeVisible()
  await expect(page.getByTestId('metrics-ribbon')).toBeVisible()
  await expect(page.getByRole('table', { name: 'Batches' })).toBeVisible()
  await expect(page.getByTestId('freshness-pill')).toContainText('All feeds current')
  await expect(page.getByTestId('demo-clock')).toContainText('12/10/2026')
  expect(errors, 'console errors').toEqual([])
})

test('F10 review: all flow cards are the same height and the "SLA · late" line never wraps at 1440 px', async ({ page }) => {
  await page.goto('/overview')
  const cards = page.locator('button[data-testid^="flow-"]')
  await expect(cards.first()).toBeVisible()
  const heights = await cards.evaluateAll((nodes) => nodes.map((node) => Math.round(node.getBoundingClientRect().height)))
  expect(new Set(heights).size, `card heights ${heights}`).toBe(1)
  const footers = page.locator('button[data-testid^="flow-"] .whitespace-nowrap')
  const lines = await footers.evaluateAll((nodes) => nodes.map((node) => Math.round(node.getBoundingClientRect().height)))
  expect(lines.length).toBeGreaterThan(0)
  expect(Math.max(...lines), `footer heights ${lines}`).toBeLessThanOrEqual(16)
  const overflowing = await footers.evaluateAll((nodes) => nodes.filter((node) => node.scrollWidth > node.clientWidth).length)
  expect(overflowing, 'footers wider than their card').toBe(0)
})
