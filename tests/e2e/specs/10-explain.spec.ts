import { expect, test } from '@playwright/test'

test('F11-AC-04: Explain on M3 lists contributing batches whose count equals the last complete week', async ({ page }) => {
  await page.goto('/overview')
  const chip = page.getByTestId('metric-M3')
  await expect(chip).toBeVisible()
  const headline = await chip.getByTestId('metric-headline').innerText() // the last complete week's %
  await chip.getByRole('button', { name: 'Explain M3' }).click()

  const popover = page.getByTestId('explain-popover')
  await expect(popover).toContainText('M3 · Sampling On-Time')
  await expect(popover).toContainText(`(${headline.replace('%', '')}`) // same week: the percentage matches the chip
  const completed = Number(await popover.locator('dt:text-is("Completed") + dd').innerText())
  expect(completed).toBeGreaterThan(0)
  await expect(popover.getByTestId('explain-rows').locator('tbody tr')).toHaveCount(completed)
  await expect(popover).toContainText('Pipeline run')
})

test('F11-FR-04: the table ⓘ appears on row hover, and a flow-card ⓘ explains the count without toggling the filter', async ({ page }) => {
  await page.goto('/overview')
  const row = page.getByTestId('batch-row').first()
  const info = row.getByRole('button', { name: 'Explain stage' })
  await expect(info).toHaveCSS('opacity', '0')
  await row.hover()
  await expect(info).toHaveCSS('opacity', '1')
  await info.click()
  await expect(page.getByTestId('explain-popover')).toContainText(/Rule R-/)
  await expect(page).not.toHaveURL(/row=/) // the click did not open the drawer
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Explain QC Testing count' }).click()
  const popover = page.getByTestId('explain-popover')
  await expect(popover).toContainText('QC Testing:')
  await expect(popover).toContainText('R-QCT')
  await expect(page).not.toHaveURL(/stage=/) // the corner ⓘ is separate from click-to-filter
})
