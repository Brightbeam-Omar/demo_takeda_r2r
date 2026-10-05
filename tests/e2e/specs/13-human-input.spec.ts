import { expect, test } from '@playwright/test'

const ROW = 'RM10031|B2077|10000782'

test('F11-FR-03: a QC lead sets and clears a status, and a planner adds a comment, from the drawer', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'quinn'))
  await page.goto(`/overview?q=B2077&row=${encodeURIComponent(ROW)}`)
  const drawer = page.getByTestId('batch-drawer')
  await expect(page.getByTestId('user-chip')).toHaveText('Quinn · QC Lead')
  await expect(drawer.getByTestId('current-status')).toContainText('none')

  await drawer.getByLabel('Status RAG').selectOption('amber')
  await drawer.getByLabel('Status team').selectOption('QC Lab')
  await expect(drawer.getByRole('button', { name: 'Set status' })).toBeDisabled() // a reason is required
  await drawer.getByLabel('Status reason').fill('Lab backlog this week')
  await drawer.getByRole('button', { name: 'Set status' }).click()
  await expect(drawer.getByTestId('current-status')).toContainText('AMBER · QC Lab')
  // The status is human input: the system RAG in the plan does not change.
  await expect(drawer.getByTestId('expected-completion')).toContainText(/GREEN|AMBER/)

  await drawer.getByRole('button', { name: 'Clear status' }).click()
  await expect(drawer.getByTestId('current-status')).toContainText('none')
  await expect(drawer.getByLabel('Add a comment')).toBeEnabled() // QC leads may comment

  // The drawer is modal, so close it to reach the persona switcher, then come back to the same row.
  await page.keyboard.press('Escape')
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('pat')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
  await page.locator(`[data-testid=batch-row][data-row-key="${ROW}"]`).click()
  await expect(drawer.getByLabel('Status RAG')).toBeDisabled()
  const note = `Chased the supplier ${Date.now()}`
  await drawer.getByLabel('Add a comment').fill(note)
  await drawer.getByRole('button', { name: 'Comment' }).click()
  await expect(drawer.getByTestId('comment-list')).toContainText(note)
})
