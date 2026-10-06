import { expect, test } from '@playwright/test'

test('F11-AC-03: the B4410 drawer timeline lists the initial lot, three earlier re-evals and the current one', async ({ page }) => {
  await page.goto('/overview?q=B4410')
  // The table shows in-flight lots only (F17-FR-10): the open re-evaluation, the one still in sampling. The four
  // released lots of the batch appear in the drawer timeline.
  await expect(page.getByTestId('batch-row')).toHaveCount(1)
  await page.getByTestId('batch-row').filter({ hasText: 'Sampling' }).click()

  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer).toBeVisible()
  const lots = drawer.getByTestId('lot-item')
  await expect(lots).toHaveCount(5)
  await expect(lots.nth(0)).toContainText('Initial')
  await expect(lots.nth(1)).toContainText('Re-eval 1')
  await expect(lots.nth(3)).toContainText('Re-eval 3')
  await expect(lots.nth(4)).toContainText('(this lot)')
  await expect(drawer.getByTestId('stage-timeline')).toBeVisible()

  // Another lot opens its own drawer, and closing leaves the table filter alone.
  await lots.nth(0).click()
  await expect(drawer.getByRole('heading', { level: 2 })).toContainText('RM10052')
  await expect(drawer.getByTestId('lot-item').nth(0)).toContainText('(this lot)')
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  await expect(page).toHaveURL(/q=B4410/)
  await expect(page).not.toHaveURL(/row=/)
})

test('F11-AC-06: the B3150 drawer shows its open major deviation and the row light is red', async ({ page }) => {
  await page.goto('/overview?q=B3150')
  const row = page.getByTestId('batch-row').first()
  await expect(row.getByRole('img', { name: 'Deviations: red' })).toBeVisible()
  await row.click()
  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer.getByRole('img', { name: 'Deviations: red' })).toBeVisible()
  const deviation = drawer.getByTestId('deviation-list').getByRole('listitem').filter({ hasText: 'Major' })
  await expect(deviation.first()).toContainText('Open')
})

test('F11-FR-07: ?row= opens the drawer even when the table filter hides that row', async ({ page }) => {
  await page.goto('/overview?q=B4410&row=' + encodeURIComponent('RM10031|B2077|10000782'))
  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer).toContainText('B2077')
  await expect(page.locator('[data-testid=batch-row][data-row-key^="RM10031|B2077|"]')).toHaveCount(0)
  await page.goto('/overview?row=' + encodeURIComponent('NOPE|B0|0'))
  await expect(page.getByTestId('batch-drawer')).toContainText('Batch not found')
})
