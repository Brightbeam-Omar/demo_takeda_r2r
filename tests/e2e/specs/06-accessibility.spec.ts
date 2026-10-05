import AxeBuilder from '@axe-core/playwright'
import { chromium, expect, test } from '@playwright/test'
import lighthouse from 'lighthouse'

const BASE = process.env.FRONTEND_URL ?? 'http://localhost:5173'

test('F10-AC-08: axe finds no serious or critical accessibility violations on the Overview', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const results = await new AxeBuilder({ page }).analyze()
  const serious = results.violations.filter((violation) => ['serious', 'critical'].includes(violation.impact ?? ''))
  expect(serious.map((violation) => `${violation.id}: ${violation.nodes.length} nodes`)).toEqual([])
})

test('F10-AC-08: Lighthouse accessibility score is at least 90 on the Overview', async () => {
  const port = 9333
  const browser = await chromium.launch({ args: [`--remote-debugging-port=${port}`] })
  try {
    const result = await lighthouse(`${BASE}/overview`, { port, onlyCategories: ['accessibility'], output: 'json', logLevel: 'error' })
    const score = (result?.lhr.categories.accessibility.score ?? 0) * 100
    expect(score, 'Lighthouse accessibility').toBeGreaterThanOrEqual(90)
  } finally {
    await browser.close()
  }
})
