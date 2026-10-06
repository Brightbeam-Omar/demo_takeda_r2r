import { expect, test } from '@playwright/test'
import { clickRow } from '../helpers'

const B2077 = 'RM10031|B2077|'

// `make seed` leaves human input in place, so start from a row without an override (a no-op on a fresh reset).
test.beforeAll(async ({ request }) => {
  await request.put(`/api/rows/${encodeURIComponent('RM10031|B2077|10000782')}/need-by`, {
    data: { adjusted_date: null, expedite: false },
    headers: { 'X-Demo-User': 'pat' },
  })
})

test('F19-AC-06 (act 5): Pat pulls B2077 forward in the Adjust Needs-by window; −7d, the deadlines and Save-needs-a-reason, then the drawer and the row update', async ({ page }) => {
  await page.goto('/overview?q=B2077')
  const row = page.locator(`[data-testid=batch-row][data-row-key^="${B2077}"]`)
  await expect(row).toBeVisible()
  await expect(row.getByTestId('expected-cell')).toContainText('15 Oct')

  await clickRow(row)
  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer).toBeVisible()
  await drawer.getByRole('button', { name: 'Open Need-by window' }).click() // a window over the open drawer

  const win = page.getByTestId('needby-window')
  await expect(win.getByTestId('system-date-box')).toHaveText('3 Dec 2026')
  await win.getByLabel('New Adjusted Date').fill('2026-11-26')
  await expect(win.getByTestId('needby-delta')).toHaveText('−7d (pulled forward)')
  await expect(win.getByTestId('needby-delta')).toHaveAttribute('data-tone', 'red')
  await expect(win.getByRole('button', { name: 'Save' })).toBeDisabled() // a date needs a reason
  await win.getByLabel('Reason for Change').selectOption('CAMPAIGN_PULLED_FORWARD')

  // Nothing is saved yet: the preview alone shows the compressed deadlines.
  const deadlines = win.getByTestId('preview-deadlines')
  await expect(deadlines).toContainText('Sampling: 14 Oct 2026')
  await expect(deadlines).toContainText('QCL Testing: 20 Nov 2026')
  await expect(deadlines).toContainText('QA Release: 26 Nov 2026')
  await expect(win.getByText('Compressed stage deadlines (preview)')).toBeVisible()

  await win.getByRole('button', { name: 'Save' }).click()
  await expect(win).toBeHidden()
  await expect(page.getByRole('status').filter({ hasText: 'Need-by updated' })).toBeVisible()
  // Closing the window left the drawer open, and its Need-by summary shows the new date, the reason and who set it.
  await expect(drawer).toBeVisible()
  const summary = drawer.getByTestId('needby-summary')
  await expect(summary).toContainText('26 Nov 2026')
  await expect(summary).toContainText('Campaign pulled forward')
  await expect(summary).toContainText('pat')
  await expect(summary).toContainText('Compressed to 88%')

  await page.keyboard.press('Escape') // close the drawer
  await expect(row).toHaveClass(/row-changed/)
  await expect(row.getByTestId('adjusted-need-by')).toContainText('26 Nov 2026')
  await expect(row.getByTestId('adjusted-need-by')).toHaveClass(/italic/)
  await expect(row.getByTestId('system-need-by')).toHaveClass(/line-through/)
  await expect(row.getByTestId('expected-cell')).toContainText('14 Oct')
  await expect(row.getByTestId('status-cell')).toHaveAttribute('data-status', 'due')

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

test('F19-AC-06: the Adjusted Date cell opens the same window straight from the table, and Other — see notes needs a note', async ({ page }) => {
  await page.goto('/overview?q=B2077')
  const row = page.locator(`[data-testid=batch-row][data-row-key^="${B2077}"]`)
  await row.getByRole('button', { name: 'Edit need-by' }).click()
  const win = page.getByTestId('needby-window')
  await expect(win).toBeVisible()
  await expect(page).toHaveURL(/win=needby/)
  await expect(page.getByTestId('batch-drawer')).toHaveCount(0) // from the table: the window alone
  await win.getByLabel('New Adjusted Date').fill('2026-11-27')
  await win.getByLabel('Reason for Change').selectOption('OTHER')
  await expect(win.getByRole('button', { name: 'Save' })).toBeDisabled()
  await win.getByLabel('Notes').fill('Agreed on the phone')
  await expect(win.getByRole('button', { name: 'Save' })).toBeEnabled()
  await page.keyboard.press('Escape')
  await expect(win).toBeHidden()
  await expect(page).not.toHaveURL(/win=/)
})
