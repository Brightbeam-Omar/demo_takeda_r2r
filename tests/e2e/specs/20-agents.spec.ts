import { expect, test } from '@playwright/test'
import { clickRow, resetAgentState } from '../helpers'

// These specs need no model: they check the Agents page, the Insights window and the drawer before any run.
test.beforeAll(() => resetAgentState())

test('F12-FR-12 a: the Agents page shows the card with model, prompt version and tools, and an empty inbox', async ({ page }) => {
  await page.goto('/overview')
  await page.getByRole('navigation', { name: 'Pages' }).getByRole('link', { name: 'Agents' }).click()
  await expect(page).toHaveURL(/\/agents$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Agents')
  const card = page.getByTestId('agent-card')
  await expect(card).toContainText('Air-gap agent')
  await expect(page.getByTestId('agent-model')).toContainText('replay')
  await expect(page.getByTestId('agent-prompt')).toHaveText('v1')
  await expect(card).toContainText('get_erp_lot')
  await expect(page.getByTestId('agent-last-run')).toHaveText('Not run yet')
  await expect(page.getByTestId('inbox')).toContainText('No proposals yet')
  // Pat (planner) may look but not run
  const run = page.getByRole('button', { name: 'Run now' })
  await expect(run).toBeDisabled()
  await expect(run).toHaveAttribute('title', 'Read-only role')
})

test('F12-FR-13: the Insights window lists the four air gaps with an empty Proposal column; Run is disabled for Pat', async ({ page }) => {
  await page.goto('/overview')
  await page.getByTestId('insights-banner').getByRole('button').click()
  const rows = page.getByTestId('window-row')
  await expect(rows).toHaveCount(4)
  await expect(page.getByRole('columnheader', { name: /Proposal/ })).toBeVisible()
  await expect(page.getByTestId('proposal-link')).toHaveCount(0)
  const run = page.getByRole('button', { name: 'Run air-gap agent' })
  await expect(run).toBeDisabled() // Pat is a planner
  await expect(run).toHaveAttribute('title', 'Read-only role')
})

test('F12-FR-13: the Run air-gap agent button is enabled for QA release', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'alex'))
  await page.goto('/overview')
  await page.getByTestId('insights-banner').getByRole('button').click()
  await expect(page.getByRole('button', { name: 'Run air-gap agent' })).toBeEnabled()
})

test('F12-FR-13: the drawer of an air-gap batch says there is no proposal yet and links to the Agents page', async ({ page }) => {
  await page.goto('/overview?q=B5003')
  const row = page.locator('[data-testid=batch-row][data-row-key*="|B5003|"]')
  await expect(row).toBeVisible()
  await clickRow(row)
  const line = page.getByTestId('batch-drawer').getByTestId('proposal-line')
  await expect(line).toContainText('Agent proposal')
  await expect(line).toContainText('None yet')
  await line.getByRole('link', { name: /Run the air-gap agent/ }).click()
  await expect(page).toHaveURL(/\/agents$/)
})
