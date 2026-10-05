import AxeBuilder from '@axe-core/playwright'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const B2077_KEY = 'RM10031|B2077|10000782'
const pat = { 'X-Demo-User': 'pat' }

// Bookmarks and presets are stored per user, so start (and finish) each test without any.
async function resetPersonal(request: APIRequestContext) {
  for (const key of (await (await request.get('/api/bookmarks', { headers: pat })).json()) as string[]) {
    await request.delete(`/api/bookmarks/${encodeURIComponent(key)}`, { headers: pat })
  }
  for (const preset of (await (await request.get('/api/presets', { headers: pat })).json()) as { id: number }[]) {
    await request.delete(`/api/presets/${preset.id}`, { headers: pat })
  }
}

test.beforeEach(async ({ request }) => resetPersonal(request))
test.afterAll(async ({ request }) => resetPersonal(request))

const rowCount = async (page: Page) => Number((await page.getByTestId('row-count').innerText()).split(' ')[0])

test('F16-AC-01: the pill panel collapses to chips, and removing a chip updates the table', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const all = await rowCount(page)

  await page.getByRole('button', { name: /Filters/ }).click()
  await expect(page).toHaveURL(/filters=open/)
  await page.getByRole('group', { name: 'Type' }).getByRole('button', { name: 'Small Molecule' }).click()
  await page.getByRole('group', { name: 'Class' }).getByRole('button', { name: 'Consumable' }).click()
  await page.getByRole('group', { name: 'Class' }).getByRole('button', { name: 'Drug Substance' }).click()
  await page.getByRole('button', { name: /Filters/ }).click()

  const chips = page.getByTestId('filter-chips')
  await expect(chips.getByText('Type: Small Molecule')).toBeVisible()
  await expect(chips.getByText('Class: 2 classes')).toBeVisible()
  const smallMolecules = await rowCount(page)
  expect(smallMolecules).toBeLessThan(all)

  await page.getByRole('button', { name: 'Remove Type: Small Molecule' }).click()
  await expect(chips.getByText('Type: Small Molecule')).toBeHidden()
  await expect(page).not.toHaveURL(/type=/)
  await expect.poll(() => rowCount(page)).toBeGreaterThan(smallMolecules)
})

test('F16-AC-02: Pat bookmarks two rows and Bookmarked shows exactly those; Quinn has none, so it is greyed', async ({ page }) => {
  await page.goto('/overview')
  const bookmarked = page.getByRole('button', { name: /^[☆★] Bookmarked$/ })
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  await expect(bookmarked).toBeDisabled()

  const rows = page.getByTestId('batch-row')
  await rows.nth(0).getByRole('button', { name: /^Bookmark / }).click()
  await expect(bookmarked).toBeEnabled()
  await rows.nth(1).getByRole('button', { name: /^Bookmark / }).click()
  await expect(page.getByRole('button', { name: /^Remove bookmark from / })).toHaveCount(2)

  await bookmarked.click()
  await expect(page).toHaveURL(/bookmarked=1/)
  await expect(page.getByTestId('row-count')).toContainText('2 lots')

  await page.getByRole('combobox', { name: 'Persona' }).selectOption('quinn')
  await expect(page.getByTestId('user-chip')).toContainText('Quinn')
  await page.getByRole('button', { name: 'Clear all' }).click()
  await expect(page.getByRole('button', { name: /^[☆★] Bookmarked$/ })).toBeDisabled()
})

test('F16-AC-03: a saved preset restores the URL and the results after everything is cleared', async ({ page }) => {
  await page.goto('/overview?type=small_molecule&class=consumable&class=drug_substance&period=this_week')
  await expect(page.getByTestId('row-count')).toBeVisible()
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const filtered = await page.getByTestId('row-count').innerText()

  await page.getByRole('button', { name: /Presets/ }).click()
  await page.getByRole('menuitem', { name: '+ Save current filters' }).click()
  await page.getByRole('textbox', { name: 'Preset name' }).fill('My small molecules')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Saved preset' })).toBeVisible()

  await page.getByRole('button', { name: 'Clear all' }).click()
  await page.goto('/overview') // everything cleared, the period back to All Dates
  await expect(page).not.toHaveURL(/small_molecule/)

  await page.getByRole('button', { name: /Presets/ }).click()
  await page.getByRole('menuitem', { name: 'My small molecules' }).click()
  await expect.poll(() => new URL(page.url()).search).toContain('type=small_molecule&class=consumable&class=drug_substance&period=this_week')
  await expect(page.getByTestId('row-count')).toHaveText(filtered)

  // A duplicate name asks before replacing.
  await page.getByRole('button', { name: /Presets/ }).click()
  await page.getByRole('menuitem', { name: '+ Save current filters' }).click()
  await page.getByRole('textbox', { name: 'Preset name' }).fill('My small molecules')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('alertdialog', { name: 'Replace existing preset?' })).toBeVisible()
})

test('F16-AC-04: after the B2077 pull-forward the banner says "1 adjusted needs-by date" and the window shows Δ −7, the reason and Pat', async ({ page, request }) => {
  await request.put(`/api/rows/${encodeURIComponent(B2077_KEY)}/need-by`, { data: { adjusted_date: null, expedite: false }, headers: pat })
  await page.goto('/overview?q=B2077')
  const banner = page.getByTestId('adjusted-banner')
  await expect(banner).toHaveAttribute('data-state', 'empty')
  await expect(banner).toContainText('No adjusted needs-by dates in this period')

  // The F11 flow: the row's pencil, a date, a reason, Save.
  const row = page.locator(`[data-testid=batch-row][data-row-key="${B2077_KEY}"]`)
  await row.click()
  await page.getByRole('button', { name: /Edit need-by/ }).click()
  const modal = page.getByTestId('need-by-modal')
  await modal.getByLabel('Adjusted need-by').fill('2026-11-26')
  await modal.getByLabel('Reason').selectOption('CAMPAIGN_PULLED_FORWARD')
  await modal.getByRole('button', { name: 'Save' }).click()
  await expect(modal).toBeHidden()
  await page.keyboard.press('Escape')

  await expect(banner).toContainText('1 adjusted needs-by date')
  await expect(banner).not.toContainText('dates')
  await banner.getByRole('button', { name: 'View details' }).click()
  const window = page.getByRole('dialog', { name: 'Adjusted Needs-by Dates — Planner Overrides' })
  await expect(window).toBeVisible()
  const entry = window.getByTestId('window-row').filter({ hasText: 'B2077' })
  await expect(entry).toContainText('RM10031')
  await expect(entry).toContainText('3 Dec 2026')
  await expect(entry).toContainText('26 Nov 2026')
  await expect(entry.getByText('−7')).toBeVisible()
  await expect(entry).toContainText('Campaign pulled forward')
  await expect(entry).toContainText('Pat')
  await expect(window.getByRole('searchbox', { name: 'Search all columns' })).toBeVisible()
  await expect(window.getByRole('button', { name: 'Reset Table' })).toBeVisible()
  await expect(window.getByRole('combobox', { name: 'Rows per page' })).toBeVisible()
})

test('F16-AC-05: the insights banner is red with 4 batches, worst-first, with B5003 last at 1d', async ({ page }) => {
  await page.goto('/overview')
  const banner = page.getByTestId('insights-banner')
  await expect(banner).toHaveAttribute('data-state', 'active')
  await expect(banner).toContainText('LIMS–SAP Insights (4 batches)')
  await banner.getByRole('button', { name: 'View all 4 →' }).click()
  const window = page.getByRole('dialog', { name: 'LIMS–SAP Insights — 4 affected batches' })
  await expect(window).toContainText('Batches where LIMS is approved but SAP has not received the result. Flagged after 24+ hours')
  const rows = window.getByTestId('window-row')
  await expect(rows).toHaveCount(4)
  const days = (await rows.locator('td:last-child').allInnerTexts()).map((text) => Number.parseInt(text, 10))
  expect(days).toEqual([...days].sort((a, b) => b - a))
  await expect(rows.last()).toContainText('B5003')
  await expect(rows.last().getByText('1d')).toBeVisible()
})

test('F16-AC-06: a campaign without air gaps turns the insights banner blue with the empty text', async ({ page }) => {
  await page.goto('/overview?campaign=CMP-DELTA')
  const banner = page.getByTestId('insights-banner')
  await expect(banner).toHaveAttribute('data-state', 'empty')
  await expect(banner).toContainText('No LIMS–SAP Insights in this period')
  await expect(banner).toHaveClass(/bg-blue-50/)
})

test('F16: axe finds no serious or critical violations with the panel open or a banner window open', async ({ page }) => {
  const serious = async () =>
    (await new AxeBuilder({ page }).analyze()).violations.filter((violation) => ['serious', 'critical'].includes(violation.impact ?? ''))
  await page.goto('/overview?filters=open')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  expect(await serious(), 'panel open').toEqual([])

  await page.getByTestId('insights-banner').getByRole('button', { name: /View all/ }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByTestId('window-row').first()).toBeVisible()
  expect(await serious(), 'insights window').toEqual([])
  await page.keyboard.press('Escape')

  await page.getByTestId('adjusted-banner').getByRole('button', { name: 'View details' }).click()
  await expect(page.getByTestId('window-row').first()).toBeVisible()
  expect(await serious(), 'adjusted window').toEqual([])
})
