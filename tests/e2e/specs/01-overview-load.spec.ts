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
  await expect(page.getByTestId('freshness-pill')).toContainText('Data current')
  await expect(page.getByTestId('demo-clock')).toContainText('Mon 12 Oct 2026')
  expect(errors, 'console errors').toEqual([])
})
