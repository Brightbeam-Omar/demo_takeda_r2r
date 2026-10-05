import { expect, test } from '@playwright/test'

test('F10-AC-04: This week switches the caption to "due in period" and keeps overdue rows', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('flow-caption')).toContainText('snapshot')
  // The first row is the most overdue one (exceptions first); it must survive the period filter.
  const overdueKey = await page.getByTestId('batch-row').first().getAttribute('data-row-key')
  expect(overdueKey).toBeTruthy()

  await page.getByTestId('period-button').click()
  await page.getByRole('button', { name: 'This Week' }).click()

  await expect(page).toHaveURL(/period=this_week/)
  await expect(page.getByTestId('flow-caption')).toContainText('due in period')
  await expect(page.locator(`[data-testid=batch-row][data-row-key="${overdueKey}"]`)).toBeVisible()
  await expect(page.getByTestId('rag-cell').filter({ hasText: 'late' }).first()).toBeVisible()
})
