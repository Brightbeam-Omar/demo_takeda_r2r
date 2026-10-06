import { expect, test } from '@playwright/test'
import { rowKeyOf } from '../helpers'

test('F19-AC-04: Quinn adds At Risk / QC Lab / Resource constraint to the status log; it tops Latest, the Status cell shows the comment, and a second entry makes History grow', async ({ page, request }) => {
  const key = await rowKeyOf(request, 'B2077')
  const before = ((await (await request.get(`/api/rows/${encodeURIComponent(key)}/status-log`, { headers: { 'X-Demo-User': 'quinn' } })).json()) as { count: number }).count
  await page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'quinn'))
  await page.goto(`/overview?q=B2077&win=status&row=${encodeURIComponent(key)}`)
  await expect(page.getByTestId('user-chip')).toHaveText('Quinn · QC Lead')
  const win = page.getByTestId('status-window')
  await expect(win.getByRole('heading', { name: 'Status Log — B2077' })).toBeVisible()
  await expect(win.getByLabel('Comment')).toBeEnabled()

  const add = win.getByRole('button', { name: 'Add Status Update' })
  await expect(add).toBeDisabled() // no comment yet
  await win.getByLabel('Status', { exact: true }).selectOption('at_risk')
  await win.getByLabel('Area / Team').selectOption('QC Lab')
  await win.getByLabel('Reason').selectOption('resource_constraint')
  const note = `Waiting for a free analyst ${Date.now()}`
  await win.getByLabel('Comment').fill(note)
  await add.click()
  const latest = win.getByTestId('status-latest')
  await expect(latest).toContainText(note)
  await expect(latest.getByTestId('status-entry-status')).toContainText('At Risk')
  await expect(latest).toContainText('QC Lab')
  await expect(latest).toContainText('Resource constraint')

  const second = `Escalated to the site lead ${Date.now()}`
  await win.getByLabel('Status', { exact: true }).selectOption('escalated')
  await win.getByLabel('Comment').fill(second)
  await add.click()
  await expect(win.getByTestId('status-latest')).toContainText(second)
  await win.getByRole('tab', { name: `History (${before + 2})` }).click()
  const history = win.getByTestId('status-history').getByTestId('status-entry-comment')
  await expect(history.nth(0)).toHaveText(second) // newest first
  await expect(history.nth(1)).toHaveText(note)

  // The plan is untouched by a status, and the Status cell shows the comment beneath the system status.
  await page.keyboard.press('Escape')
  const row = page.locator(`[data-testid=batch-row][data-row-key="${key}"]`)
  await expect(row.getByTestId('status-comment')).toContainText(second)
  await expect(row.getByTestId('status-cell')).toHaveAttribute('data-status', /due|ok|late/)
})

test('F19-FR-05: a planner (not only QC) can add a status; the drawer summary shows the latest entry with the history count', async ({ page, request }) => {
  const key = await rowKeyOf(request, 'B1042')
  await page.goto(`/overview?q=B1042&row=${encodeURIComponent(key)}`)
  const drawer = page.getByTestId('batch-drawer')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
  await drawer.getByRole('button', { name: 'Open Status log window' }).click()
  const win = page.getByTestId('status-window')
  const note = `Chased the lab ${Date.now()}`
  await win.getByLabel('Comment').fill(note)
  await win.getByRole('button', { name: 'Add Status Update' }).click()
  await expect(win.getByTestId('status-latest')).toContainText(note)
  await win.getByRole('form', { name: 'Add a status update' }).getByRole('button', { name: 'Close' }).click()
  await expect(win).toBeHidden()
  await expect(drawer.getByTestId('status-summary')).toContainText(note)
  await expect(drawer.getByTestId('status-summary')).toContainText(/\d+ entries in the log/)
})
