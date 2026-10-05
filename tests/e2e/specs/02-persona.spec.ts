import { expect, test } from '@playwright/test'

test('F10-AC-02: switching to Sam shows "Sam · Viewer" and disables the edit buttons', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
  await expect(page.getByRole('button', { name: 'Edit need-by' }).first()).toBeEnabled()

  await page.getByRole('combobox', { name: 'Persona' }).selectOption('sam')

  await expect(page.getByTestId('user-chip')).toHaveText('Sam · Viewer')
  const pencil = page.getByRole('button', { name: 'Edit need-by' }).first()
  await expect(pencil).toBeDisabled()
  await expect(pencil).toHaveAttribute('title', 'Read-only role')
  expect(await page.evaluate(() => sessionStorage.getItem('r2r.persona'))).toBe('sam')
  // The persona survives a reload within the session, and Pat comes back with a fresh one.
  await page.reload()
  await expect(page.getByTestId('user-chip')).toHaveText('Sam · Viewer')
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('pat')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
})
