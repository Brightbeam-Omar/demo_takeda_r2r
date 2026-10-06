import { expect, test } from '@playwright/test'

test('F10-AC-03: clicking QCL Testing filters the table, puts stage= in the URL and survives a reload', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()

  await page.getByTestId('flow-qc_testing').click()

  await expect(page).toHaveURL(/stage=qc_testing/)
  await expect(page.getByTestId('flow-qc_testing')).toHaveAttribute('aria-pressed', 'true')
  const count = await page.getByTestId('flow-qc_testing').locator('div').nth(2).innerText()
  await expect(page.getByTestId('row-count')).toContainText(`${count} lots`)
  for (const cell of await page.getByTestId('batch-row').locator('[role=cell]:nth-child(8)').allInnerTexts()) {
    expect(cell).toContain('QCL Testing')
  }

  await page.reload()
  await expect(page).toHaveURL(/stage=qc_testing/)
  await expect(page.getByTestId('flow-qc_testing')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('row-count')).toContainText(`${count} lots`)
})

test('F17-AC-02: Sampling + QCL Ship + QCL Testing filter the table, the card counts stay, and three chips appear', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const before = await page.locator('button[data-testid^="flow-"]').evaluateAll((nodes) => nodes.map((node) => node.textContent))
  await expect(page.getByTestId('flow-total')).toHaveAttribute('aria-pressed', 'true')
  for (const stage of ['sampling', 'qc_ship', 'qc_testing']) await page.getByTestId(`flow-${stage}`).click()
  await expect(page).toHaveURL(/stage=sampling&stage=qc_ship&stage=qc_testing/)
  await expect(page.getByTestId('flow-total')).toHaveAttribute('aria-pressed', 'false')
  await expect(page.getByRole('button', { name: '✕ Clear 3 stages' })).toBeVisible()
  await expect(page.getByTestId('filter-chips').getByText(/^Stage: /)).toHaveCount(3)
  await expect(page.getByTestId('showing-line')).toContainText('3 stages selected')
  const after = await page.locator('button[data-testid^="flow-"]').evaluateAll((nodes) => nodes.map((node) => node.textContent))
  expect(after).toEqual(before)
  const counts = await Promise.all(['sampling', 'qc_ship', 'qc_testing'].map(async (s) => Number(await page.getByTestId(`flow-${s}`).locator('div').nth(2).innerText())))
  await expect(page.getByTestId('row-count')).toContainText(`${counts.reduce((a, b) => a + b, 0)} lots`)
  await page.getByRole('button', { name: '✕ Clear 3 stages' }).click()
  await expect(page).not.toHaveURL(/stage=/)
  await expect(page.getByTestId('flow-total')).toHaveAttribute('aria-pressed', 'true')
})

test('F17-AC-01 / AC-08: Expected Delivery shows the open PO lines, Total Pipeline shows 482, and the table shows 482 in-flight lots', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  await expect(page.getByTestId('flow-total')).toContainText('482')
  await expect(page.getByTestId('active-batches')).toHaveText('482 active batches')
  await expect(page.getByTestId('row-count')).toContainText('482 lots')
  const lines = Number(await page.getByTestId('expected-delivery-count').innerText())
  expect(lines).toBeGreaterThanOrEqual(60)
  expect(lines).toBeLessThanOrEqual(90)
  await page.getByTestId('flow-expected-delivery').click()
  await expect(page.getByRole('dialog')).toContainText(`${lines} open PO lines`)
  await expect(page.getByTestId('window-row').first()).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByTestId('flow-released').click()
  await expect(page.getByTestId('row-count')).toContainText('321 lots')
})

test('F17-AC-03: the Call Off and QCL Ship cards show their skip counts, and Pending has no card', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('skip-qc_ship')).toContainText(/^\d+ skip /)
  await expect(page.getByTestId('flow-pending')).toHaveCount(0)
  await expect(page.getByTestId('skip-call_off')).toContainText(/^\d+ skip call-off$/)
})

test('F17-FR-10: the RELEASED tag shows the 321 released lots, like the Released card', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  await page.getByTestId('tag-released').click()
  await expect(page.getByTestId('row-count')).toContainText('321 lots')
})
