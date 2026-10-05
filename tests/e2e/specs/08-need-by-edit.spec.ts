import { expect, test } from '@playwright/test'

const B2077 = 'RM10031|B2077|'

// `make seed` leaves human input in place, so start from a row without an override (a no-op on a fresh reset).
test.beforeAll(async ({ request }) => {
  await request.put(`/api/rows/${encodeURIComponent('RM10031|B2077|10000782')}/need-by`, {
    data: { adjusted_date: null, expedite: false },
    headers: { 'X-Demo-User': 'pat' },
  })
})

test('F11-AC-01: Pat pulls B2077 forward; the preview shows 6/37/6 and 14 Oct amber before save, then the row is italic and highlighted', async ({ page }) => {
  await page.goto('/overview?q=B2077')
  const row = page.locator(`[data-testid=batch-row][data-row-key^="${B2077}"]`)
  await expect(row).toBeVisible()
  await expect(row.getByTestId('rag-cell')).toContainText('15 Oct')

  await row.click()
  await expect(page.getByTestId('batch-drawer')).toBeVisible()
  await page.getByRole('button', { name: /Edit need-by/ }).click()

  const modal = page.getByTestId('need-by-modal')
  await expect(modal.getByTestId('system-date-box')).toHaveText('3 Dec 2026')
  await modal.getByLabel('Adjusted need-by').fill('2026-11-26')
  await expect(modal.getByRole('button', { name: 'Save' })).toBeDisabled() // a date needs a reason
  await modal.getByLabel('Reason').selectOption('CAMPAIGN_PULLED_FORWARD')

  // Nothing is saved yet: the preview alone shows the new plan.
  await expect(modal.getByTestId('preview-expected')).toContainText('14 Oct 2026')
  await expect(modal.getByTestId('preview-rag')).toHaveText('AMBER')
  await expect(modal.getByTestId('preview-compression')).toContainText('Sampling 6 d / QC Testing 37 d / QA Release 6 d')

  await modal.getByRole('button', { name: 'Save' }).click()
  await expect(modal).toBeHidden()
  await expect(page.getByRole('status').filter({ hasText: 'Need-by updated' })).toBeVisible()
  await page.keyboard.press('Escape') // close the drawer
  await expect(row).toHaveClass(/row-changed/)
  await expect(row.getByTestId('adjusted-need-by')).toHaveText('26 Nov')
  await expect(row.getByTestId('adjusted-need-by')).toHaveClass(/italic/)
  await expect(row.getByTestId('system-need-by')).toHaveClass(/line-through/)
  await expect(row.getByTestId('rag-cell')).toContainText('14 Oct')
  await expect(row.getByTestId('rag-cell')).toHaveAttribute('data-rag', 'amber')

  // The audit log has the entry with its old and new values.
  await page.getByRole('link', { name: 'Audit Log' }).click()
  const entry = page.locator('[data-testid=audit-entry][data-action=need_by_set]').first()
  await expect(entry).toContainText('pat')
  await expect(entry).toContainText(B2077)
  await entry.getByRole('button', { name: /Show details/ }).click()
  const details = page.getByTestId('audit-details')
  await expect(details).toContainText('system date → 26 Nov 2026')
  await expect(details).toContainText('Campaign pulled forward')
})
