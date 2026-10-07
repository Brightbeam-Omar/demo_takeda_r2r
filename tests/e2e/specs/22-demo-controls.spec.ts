import { expect, test, type Page } from '@playwright/test'

// F13-FR-06 / AC-04: the Demo Controls page. It resets the demo (about a minute), so it runs once, serially, and
// leaves the demo in its starting state. The reset is the only way to get a known state whatever ran before.
test.describe.configure({ mode: 'serial' })
test.setTimeout(240_000)

const asAdmin = (page: Page) => page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'admin'))
const status = (page: Page) => page.getByTestId('run-status')

test('F13-AC-04: only an admin sees Demo Controls; a planner gets the notice and no controls', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByRole('link', { name: 'Demo Controls' })).toHaveCount(0) // Pat, a planner
  await page.goto('/admin/demo')
  await expect(page.getByTestId('demo-forbidden')).toContainText('for admins')
  await expect(page.getByRole('button', { name: 'Reset demo' })).toHaveCount(0)
})

test('F13-AC-04: Reset demo asks first, then shows the progress live and leaves a clean demo', async ({ page }) => {
  await asAdmin(page)
  await page.goto('/admin/demo')
  await expect(page.getByTestId('demo-step')).toHaveCount(9)
  await page.getByRole('button', { name: 'Reset demo' }).click()
  await page.getByTestId('confirm-dialog').getByRole('button', { name: 'Reset demo' }).click()
  await expect(status(page)).toHaveAttribute('data-status', 'running')
  await expect(page.getByTestId('progress-line').filter({ hasText: 'Wipe the lakehouse' })).toBeVisible() // before the end
  await expect(status(page)).toHaveAttribute('data-status', 'succeeded', { timeout: 180_000 })
  const last = page.getByTestId('progress-line').last()
  await expect(last).toContainText('Demo reset:')
  await expect(last).toContainText('4 air gaps')
  await expect(last).toContainText('0 proposals')
})

test('F13-AC-02: lims-approve-B1042 moves B1042 to QA Release, and a second run says why it cannot', async ({ page }) => {
  await asAdmin(page)
  await page.goto('/admin/demo')
  const step = page.locator('[data-step="lims-approve-B1042"]')
  await expect(step.getByTestId('precondition-light')).toHaveAttribute('data-state', 'met')
  await step.getByRole('button', { name: /^Run / }).click()
  await expect(page.getByTestId('progress-line').filter({ hasText: '[1/3] LIMS: approve the sample' })).toBeVisible()
  await expect(status(page)).toHaveAttribute('data-status', 'succeeded', { timeout: 90_000 })
  await expect(step.getByTestId('precondition-light')).toHaveAttribute('data-state', 'unmet')

  await step.getByRole('button', { name: /^Run / }).click()
  await expect(page.getByTestId('step-refused')).toContainText('already been approved in LIMS')

  await page.goto('/overview?q=B1042')
  await expect(page.getByTestId('batch-row').filter({ hasText: 'B1042' })).toContainText('QA Release')
})

test('F13-AC-03: ud-post-B5003 takes B5003 out of the Insights banner', async ({ page }) => {
  await asAdmin(page)
  await page.goto('/overview')
  await expect(page.getByTestId('insights-banner')).toContainText('LIMS–SAP Insights (4 batches)')
  await page.goto('/admin/demo')
  await page.locator('[data-step="ud-post-B5003"]').getByRole('button', { name: /^Run / }).click()
  await expect(status(page)).toHaveAttribute('data-status', 'succeeded', { timeout: 90_000 })
  await page.goto('/overview')
  await expect(page.getByTestId('insights-banner')).toContainText('LIMS–SAP Insights (3 batches)')
})

test('F13-FR-06: the last test puts the demo back to its starting state', async ({ page }) => {
  await asAdmin(page)
  await page.goto('/admin/demo')
  await page.getByRole('button', { name: 'Reset demo' }).click()
  await page.getByTestId('confirm-dialog').getByRole('button', { name: 'Reset demo' }).click()
  await expect(status(page)).toHaveAttribute('data-status', 'succeeded', { timeout: 180_000 })
  await page.goto('/overview')
  await expect(page.getByTestId('insights-banner')).toContainText('LIMS–SAP Insights (4 batches)')
})
