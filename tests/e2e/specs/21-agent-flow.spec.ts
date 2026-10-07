import { expect, test } from '@playwright/test'
import { clickRow, hasRecordings, resetAgentState } from '../helpers'

// The run needs the model's recorded answers (`make record-agents`); the specs say so and skip until they exist.
test.skip(!hasRecordings(), 'no recordings yet: run `make record-agents` (needs ANTHROPIC_API_KEY with credit)')
test.describe.configure({ mode: 'serial' })
test.beforeAll(() => resetAgentState())

test('F12-AC-01 (act 6): Alex runs the agent from the Insights window; B5003 gets a pending proposal that passes V1 to V6', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'alex'))
  await page.goto('/overview')
  await page.getByTestId('insights-banner').getByRole('button').click()
  await page.getByRole('button', { name: 'Run air-gap agent' }).click()
  await expect(page.getByTestId('run-result')).toContainText('4 proposals created.')
  const rows = page.getByTestId('window-row')
  await expect(rows.filter({ hasText: 'Pending approval' })).toHaveCount(4)
  const b5003 = rows.filter({ hasText: 'B5003' })
  await b5003.getByTestId('proposal-link').click()
  await expect(page).toHaveURL(/\/agents\/proposals\/\d+$/)
  await expect(page.getByRole('heading', { name: /Air-gap ticket for B5003/ })).toBeVisible()
  await expect(page.getByTestId('evidence-table')).toBeVisible()
  const checks = page.getByTestId('evidence-row').locator('[data-verified]')
  await expect(checks.first()).toHaveAttribute('data-verified', 'true')
  for (const id of ['V1', 'V2', 'V3', 'V4', 'V5', 'V6']) await expect(page.getByTestId(`rule-${id}`)).toHaveAttribute('data-passed', 'true')
})

test('F12-AC-02: Pat cannot approve; Alex approves and the ticket and the outbox email appear', async ({ page }) => {
  await page.goto('/agents')
  await page.getByTestId('proposal-row').filter({ hasText: 'B5003' }).click()
  await expect(page.getByRole('button', { name: 'Approve' })).toBeDisabled() // Pat
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('alex')
  const approve = page.getByRole('button', { name: 'Approve' })
  await expect(approve).toBeEnabled()
  await approve.click()
  const preview = page.getByTestId('executed-preview')
  await expect(preview).toBeVisible()
  await expect(preview.getByTestId('delivery')).toHaveText('Sent to outbox (demo)')
  await expect(preview.getByTestId('email-subject')).toContainText('B5003')
  await expect(page.getByTestId('decided-line')).toContainText('Approved by alex')
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('pat')
})

test('F12-AC-05: the trace shows input, three or more tool calls across two systems, model calls, validation, decision, action', async ({ page }) => {
  await page.goto('/agents')
  await page.getByTestId('proposal-row').filter({ hasText: 'B5003' }).getByRole('link', { name: /TR-/ }).click()
  await expect(page).toHaveURL(/\/agents\/traces\/TR-\d+$/)
  await expect(page.getByTestId('trace-step').first()).toBeVisible()
  const kinds = await page.getByTestId('trace-step').evaluateAll((items) => items.map((i) => i.getAttribute('data-step-type')))
  expect(kinds[0]).toBe('input')
  expect(kinds.filter((k) => k === 'tool_call').length).toBeGreaterThanOrEqual(3)
  expect(kinds.indexOf('model_request')).toBeLessThan(kinds.indexOf('tool_call'))
  expect(kinds.slice(-6)).toEqual(['validation', 'decision', 'action', 'validation', 'decision', 'action'])
  await expect(page.getByTestId('trace-provider')).toContainText('replay')
  await expect(page.getByTestId('trace-totals')).toContainText('Cost estimate')
})

test('F12-AC-06: running again creates no duplicate; the drawer shows the executed proposal', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'alex'))
  await page.goto('/agents')
  await page.getByRole('button', { name: 'Run now' }).click()
  await expect(page.getByTestId('run-result')).toContainText('Nothing new to propose')
  await page.goto('/overview?q=B5003')
  await clickRow(page.locator('[data-testid=batch-row][data-row-key*="|B5003|"]'))
  await expect(page.getByTestId('batch-drawer').getByTestId('proposal-line')).toContainText('Executed')
})
