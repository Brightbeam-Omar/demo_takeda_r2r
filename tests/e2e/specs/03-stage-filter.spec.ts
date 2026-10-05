import { expect, test } from '@playwright/test'

test('F10-AC-03: clicking QC Testing filters the table, puts stage= in the URL and survives a reload', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()

  await page.getByTestId('flow-qc_testing').click()

  await expect(page).toHaveURL(/stage=qc_testing/)
  await expect(page.getByTestId('flow-qc_testing')).toHaveAttribute('aria-pressed', 'true')
  const count = await page.getByTestId('flow-qc_testing').locator('div').nth(1).innerText()
  await expect(page.getByTestId('row-count')).toHaveText(`${count} batches`)
  for (const cell of await page.getByTestId('batch-row').locator('[role=cell]:nth-child(7)').allInnerTexts()) {
    expect(cell).toContain('QC Testing')
  }

  await page.reload()
  await expect(page).toHaveURL(/stage=qc_testing/)
  await expect(page.getByTestId('flow-qc_testing')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('row-count')).toHaveText(`${count} batches`)
})
