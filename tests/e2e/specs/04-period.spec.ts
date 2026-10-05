import { expect, test } from '@playwright/test'

test('F10-AC-04: This week switches the caption to "due in period" and keeps overdue rows', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('flow-caption')).toContainText('snapshot')

  await page.getByRole('button', { name: 'Period' }).click()
  await page.getByRole('menuitemradio', { name: 'This week' }).click()

  await expect(page).toHaveURL(/period=this_week/)
  await expect(page.getByTestId('flow-caption')).toContainText('due in period')
  await expect(page.getByTestId('rag-cell').filter({ hasText: 'late' }).first()).toBeVisible()
})
