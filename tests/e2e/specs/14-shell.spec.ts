import { readdirSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { REPO_ROOT } from '../helpers'

const VIEWS = ['Overview', 'Reports & Metrics', 'Agents']
// The demo hides the four Tier 2 placeholders (F14-FR-16, profile demo.hide_placeholders).
const PLACEHOLDERS = ['Upload Data', 'Process / Campaign Mapping', 'POC — Integrations', 'Configuration']
const ADMIN = [
  'Team Dashboard', 'Audit Log', 'Schema Reference', 'SLA Configuration', 'Sync Status', 'Webhook Sync Status',
  'Feedback',
]

test('F15-AC-01: the sidebar has VIEWS and ADMIN with every item and the ALPHA – LOCAL badge', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const sidebar = page.getByTestId('sidebar')
  await expect(sidebar.getByText('VIEWS', { exact: true })).toBeVisible()
  await expect(sidebar.getByText('ADMIN', { exact: true })).toBeVisible()
  for (const label of [...VIEWS, ...ADMIN]) await expect(sidebar.getByRole('link', { name: label, exact: true })).toBeVisible()
  for (const label of PLACEHOLDERS) await expect(sidebar.getByRole('link', { name: label, exact: true })).toHaveCount(0)
  await expect(page.getByTestId('release-badge')).toHaveText('ALPHA – LOCAL')
  await expect(sidebar.getByText('Phase 1: Trusted Data')).toBeVisible()
  // Demo Controls: DEMO_MODE and admin only
  await expect(sidebar.getByRole('link', { name: 'Demo Controls' })).toHaveCount(0)
  // The top bar: page title, feed pill, period, date-time and the user chip.
  await expect(page.getByRole('heading', { name: 'R2R Overview' })).toBeVisible()
  await expect(page.getByTestId('freshness-pill')).toContainText('last sync')
  await expect(page.getByTestId('demo-clock')).toHaveText(/^\d\d\/\d\d\/\d{4} \d\d:\d\d$/)
  await expect(page.getByTestId('feedback-button')).toBeVisible()
  await page.screenshot({ path: join(REPO_ROOT, 'docs/screenshots/shell.png') })

  await page.getByRole('combobox', { name: 'Persona' }).selectOption('admin')
  await expect(sidebar.getByRole('link', { name: 'Demo Controls' })).toBeVisible()
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('pat')
})

test('F14-FR-16: with the flag off the four Tier 2 placeholders are in the menu', async ({ page }) => {
  await page.route('**/api/reference', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    await route.fulfill({ response, json: { ...body, demo: { ...body.demo, hide_placeholders: false } } })
  })
  await page.goto('/overview')
  for (const label of PLACEHOLDERS) await expect(page.getByTestId('sidebar').getByRole('link', { name: label, exact: true })).toBeVisible()
})

test('F15-AC-02: Last Month applies, and a custom range needs two clicks before Apply', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const allCount = await page.getByTestId('page-summary').innerText()

  await page.getByTestId('period-button').click()
  await page.getByRole('button', { name: 'Last Month' }).click()
  await expect(page).toHaveURL(/period=last_month/)
  await expect(page.getByTestId('period-button')).toContainText('Last Month')
  await expect(page.getByTestId('flow-caption')).toContainText(/due in period/i)
  await expect(page.getByTestId('page-summary')).not.toHaveText(allCount)

  await page.getByTestId('period-button').click()
  await expect(page.getByRole('button', { name: 'Last Month', pressed: true })).toBeVisible()
  await expect(page.getByTestId('period-hint')).toHaveText('Click a date to start')
  await expect(page.getByRole('button', { name: 'Apply' })).toBeDisabled()
  await page.getByRole('button', { name: '1 Oct 2026', exact: true }).click()
  await expect(page.getByTestId('period-hint')).toHaveText('Click an end date')
  await expect(page.getByRole('button', { name: 'Apply' })).toBeDisabled()
  await page.getByRole('button', { name: '31 Oct 2026', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Apply' })).toBeEnabled()
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page).toHaveURL(/period=custom&from=2026-10-01&to=2026-10-31/)
  await expect(page.getByTestId('period-button')).toContainText('1 Oct 2026 – 31 Oct 2026')
})

test('F15-AC-03: site_a reads SAP BLOCKED and QCL Testing; a profile with erp "ERP" reads ERP BLOCKED', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'SAP BLOCKED' })).toBeVisible()
  await expect(page.getByTestId('flow-qc_testing')).toContainText('QCL Testing')

  // The same page against a reference whose terms come from a different profile: no code change.
  await page.route('**/api/reference', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    body.terms = { ...body.terms, erp: 'ERP', erp_blocked_tag: 'ERP BLOCKED' }
    await route.fulfill({ response, json: body })
  })
  await page.reload()
  await expect(page.getByRole('button', { name: 'ERP BLOCKED' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'SAP BLOCKED' })).toHaveCount(0)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
})

test('F15-AC-04: feedback posted by Sam is stored and listed for Admin', async ({ page }) => {
  const message = `Shell feedback ${Date.now()}`
  await page.goto('/admin/audit')
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('sam')
  await expect(page.getByTestId('user-chip')).toHaveText('Sam · Viewer')
  await page.getByTestId('feedback-button').click()
  await expect(page.getByTestId('feedback-page')).toHaveText('/admin/audit')
  await page.getByLabel('Feedback message').fill(message)
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'feedback was sent' })).toBeVisible()

  await page.getByTestId('nav-admin-feedback').click()
  await expect(page.getByText('Feedback is visible to the Admin role only.')).toBeVisible()
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('admin')
  const row = page.getByTestId('feedback-row').filter({ hasText: message })
  await expect(row).toBeVisible()
  await expect(row).toContainText('sam')
  await expect(row).toContainText('/admin/audit')
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('pat')
})

test('F15-AC-05: no Inter font is requested and the page uses DM Sans', async ({ page }) => {
  const fonts: string[] = []
  page.on('request', (request) => request.resourceType() === 'font' && fonts.push(request.url()))
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  expect(fonts.filter((url) => /inter/i.test(url)), `fonts: ${fonts}`).toEqual([])
  expect(fonts.some((url) => /dm-sans/i.test(url)), `fonts: ${fonts}`).toBe(true)
  const family = await page.evaluate(() => getComputedStyle(document.body).fontFamily)
  expect(family).toContain('DM Sans')
  // Lighthouse accessibility >= 90 is asserted by 06-accessibility.spec.ts, which now runs against this shell.
})

test('F15-AC-06: no client logo asset exists in frontend/', async () => {
  const files: string[] = []
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === 'node_modules' || entry.name === 'dist') continue
      const path = join(dir, entry.name)
      if (entry.isDirectory()) walk(path)
      else files.push(path)
    }
  }
  walk(join(REPO_ROOT, 'frontend'))
  expect(files.filter((file) => /logo/i.test(file.split('/').pop() ?? ''))).toEqual([])
  // Only the generic mark, drawn in markup: nothing but the favicon and text is shipped as an image.
  expect(files.filter((file) => /\.(png|jpe?g|svg|gif|webp)$/i.test(file) && !/favicon/i.test(file))).toEqual([])
})

test('F15 review: no stray "." in the stage cell, and the Feedback button never covers the last rows', async ({ page }) => {
  await page.goto('/overview?stage=sampling')
  const row = page.getByTestId('batch-row').first()
  await expect(row).toBeVisible()
  await page.mouse.move(0, 0)
  // The hover-only explain button must not leave an ellipsis behind: the stage cell clips, it does not truncate.
  const overflow = await row.locator('td').nth(8).evaluate((node) => getComputedStyle(node).textOverflow)
  expect(overflow).toBe('clip')

  // Scrolled to the bottom, the page content ends above the floating button.
  await page.evaluate(() => document.querySelector('main')?.scrollTo(0, 1e6))
  const main = await page.locator('main').evaluate((node) => {
    const last = node.lastElementChild?.getBoundingClientRect()
    return { bottom: last?.bottom ?? 0 }
  })
  const button = await page.getByTestId('feedback-button').boundingBox()
  expect(main.bottom).toBeLessThanOrEqual(button?.y ?? 0)
})
