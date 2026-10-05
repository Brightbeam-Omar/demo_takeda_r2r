import { expect, test } from '@playwright/test'

test('F10-AC-06: M1, M2, M4 and M5 are compact "Mx · Tier 2" chips with the reason as a tooltip', async ({ page }) => {
  await page.goto('/overview')
  for (const id of ['M1', 'M2', 'M4', 'M5']) {
    const chip = page.getByTestId(`metric-${id}`)
    await expect(chip).toHaveText(`${id} · Tier 2`)
    await expect(chip).toHaveAttribute('title', /enabled in Tier 2/)
  }
  await expect(page.getByTestId('metric-M3').getByTestId('metric-headline')).toContainText('%')
})
