import { expect, test } from '@playwright/test'

test('F11-AC-02: as Sam the drawer has no enabled edit controls, and a forced API call is refused with 403', async ({ page, request }) => {
  await page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'sam'))
  await page.goto('/overview?q=B2077')
  const row = page.locator('[data-testid=batch-row][data-row-key^="RM10031|B2077|"]')
  await row.click()
  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer).toBeVisible()
  await expect(page.getByTestId('user-chip')).toHaveText('Sam · Viewer')

  await expect(drawer.getByRole('button', { name: /Edit need-by/ })).toBeDisabled()
  await expect(drawer.getByRole('button', { name: /Edit need-by/ })).toHaveAttribute('title', 'Read-only role')
  await expect(drawer.getByLabel('Status RAG')).toBeDisabled()
  await expect(drawer.getByRole('button', { name: 'Set status' })).toBeDisabled()
  await expect(drawer.getByLabel('Add a comment')).toBeDisabled()
  await expect(drawer.getByRole('button', { name: 'Comment' })).toBeDisabled()

  const key = encodeURIComponent('RM10031|B2077|10000782')
  const forced = await request.put(`/api/rows/${key}/need-by`, {
    data: { adjusted_date: '2026-11-26', reason_code: 'CAMPAIGN_PULLED_FORWARD' },
    headers: { 'X-Demo-User': 'sam' },
  })
  expect(forced.status()).toBe(403)
})
