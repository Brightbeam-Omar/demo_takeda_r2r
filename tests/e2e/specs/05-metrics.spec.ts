import { expect, test } from '@playwright/test'

test('F10-AC-06 / F17-FR-06: M1, M2, M4 and M5 read N/A with the reason in the tooltip', async ({ page }) => {
  await page.goto('/overview')
  for (const id of ['M1', 'M2', 'M4', 'M5']) {
    const card = page.getByTestId(`metric-${id}`)
    await expect(card.getByTestId('metric-headline')).toHaveText('N/A')
    await expect(card.getByTestId('metric-info')).toHaveAttribute('title', /enabled in Tier 2/)
  }
  await expect(page.getByTestId('metric-M3').getByTestId('metric-headline')).toContainText('%')
})

test('F17-AC-04: the header reads Week 41 (2026) and M3 is 94% green, M6 84% amber, M7 69% red with their counts', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByRole('region', { name: /Week 41 \(2026\) — 7 R2R Metrics/ })).toBeVisible()
  await expect(page.getByText('Source: weekly_metrics_v')).toBeVisible()
  const expected = { M3: ['94%', 'green', '17/18'], M6: ['84%', 'amber', '36/43'], M7: ['69%', 'red', '9/13'] }
  for (const [id, [pct, rag, counts]] of Object.entries(expected)) {
    const card = page.getByTestId(`metric-${id}`)
    await expect(card.getByTestId('metric-headline')).toHaveText(pct as string)
    await expect(card).toHaveAttribute('data-rag', rag as string)
    await expect(card.getByTestId('metric-counts')).toContainText(counts as string)
  }
})

test('F17-AC-05: ON HOLD + EXPEDITE show rows with either, Clear tags restores everything, and no alert band exists', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  await expect(page.getByTestId('page-summary')).toContainText('482 lots')
  await page.getByTestId('tag-on_hold').click()
  await page.getByTestId('tag-expedite').click()
  await expect(page).toHaveURL(/flag=on_hold&flag=expedite/)
  const filtered = Number((await page.getByTestId('page-summary').innerText()).match(/(\d+) lots/)?.[1])
  expect(filtered).toBeGreaterThan(0)
  expect(filtered).toBeLessThan(482)
  await page.getByRole('button', { name: 'Clear tags' }).click()
  await expect(page.getByTestId('page-summary')).toContainText('482 lots')
  await expect(page.getByTestId('alert-late')).toHaveCount(0)
})
