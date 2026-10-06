import { expect, test } from '@playwright/test'
import { clickRow } from '../helpers'

test('F11-AC-02 / F19: as Sam the windows have no enabled edit controls, and forced API calls are refused with 403', async ({ page, request }) => {
  await page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'sam'))
  await page.goto('/overview?q=B2077')
  const row = page.locator('[data-testid=batch-row][data-row-key^="RM10031|B2077|"]')
  await clickRow(row)
  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer).toBeVisible()
  await expect(page.getByTestId('user-chip')).toHaveText('Sam · Viewer')

  await drawer.getByRole('button', { name: 'Open Need-by window' }).click()
  const needBy = page.getByTestId('needby-window')
  await expect(needBy.getByLabel('New Adjusted Date')).toBeDisabled()
  await expect(needBy.getByLabel('Reason for Change')).toBeDisabled()
  await expect(needBy.getByRole('button', { name: 'Save' })).toBeDisabled()
  await expect(needBy.getByRole('button', { name: 'Save' })).toHaveAttribute('title', 'Read-only role')
  await page.keyboard.press('Escape')

  await drawer.getByRole('button', { name: 'Open Status log window' }).click()
  const status = page.getByTestId('status-window')
  await expect(status.getByLabel('Comment')).toBeDisabled()
  await expect(status.getByLabel('Status', { exact: true })).toBeDisabled()
  await expect(status.getByRole('button', { name: 'Add Status Update' })).toBeDisabled()
  await expect(status.getByRole('button', { name: 'Add Status Update' })).toHaveAttribute('title', 'Read-only role')

  const key = encodeURIComponent('RM10031|B2077|10000782')
  const forced = await request.put(`/api/rows/${key}/need-by`, {
    data: { adjusted_date: '2026-11-26', reason_code: 'CAMPAIGN_PULLED_FORWARD' },
    headers: { 'X-Demo-User': 'sam' },
  })
  expect(forced.status()).toBe(403)
  const forcedLog = await request.post(`/api/rows/${key}/status-log`, {
    data: { status: 'at_risk', comment: 'forced' },
    headers: { 'X-Demo-User': 'sam' },
  })
  expect(forcedLog.status()).toBe(403)
})
