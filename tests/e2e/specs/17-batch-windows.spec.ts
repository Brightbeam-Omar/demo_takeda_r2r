import { expect, test, type APIRequestContext } from '@playwright/test'
import { rowKeyOf } from '../helpers'

// F19 acceptance tests for the Inbound and Sample Data windows on the live stack (make up, make seed).
const alex = { 'X-Demo-User': 'alex' }

interface Detail {
  row_key: string
  inbound_check: { status: string; failed_count: number } | null
}

/** The first in-flight row whose inbound check has the given status (found through the API, never hard-coded). */
async function rowWithInbound(request: APIRequestContext, status: string): Promise<Detail> {
  const { rows } = (await (await request.get('/api/overview', { headers: alex })).json()) as { rows: { row_key: string; inbound_light: string }[] }
  for (const row of rows) {
    const detail = (await (await request.get(`/api/rows/${encodeURIComponent(row.row_key)}`, { headers: alex })).json()) as Detail
    if (detail.inbound_check?.status === status) return detail
  }
  throw new Error(`no in-flight row with a ${status} inbound check in the seed`)
}

test('F19-AC-02: a failed inbound check shows Failed, Failed checks: n and the FAIL items in red', async ({ page, request }) => {
  const detail = await rowWithInbound(request, 'failed')
  await page.goto(`/overview?win=inbound&row=${encodeURIComponent(detail.row_key)}`)
  const win = page.getByTestId('inbound-window')
  await expect(win.getByTestId('inbound-result')).toContainText('Failed')
  await expect(win.getByRole('img', { name: 'Inbound check: red' })).toBeVisible()
  await expect(win.getByTestId('failed-checks')).toContainText(`Failed checks: ${detail.inbound_check!.failed_count}`)
  await expect(win.getByText('SAP lot number')).toBeVisible() // the profile term for the ERP
  const failing = win.getByTestId('inbound-items').locator('[data-outcome=FAIL]')
  await expect(failing.first()).toBeVisible()
  await expect(failing.first().locator('span').last()).toHaveClass(/text-red-700/)
  await expect(win.getByTestId('inbound-verdict')).toHaveText('Failed')
})

test('F19-AC-02: a resolved check shows the amber dot and Completed (Resolved); the table dot opens the window', async ({ page, request }) => {
  const detail = await rowWithInbound(request, 'resolved')
  await page.goto('/overview')
  await page.getByRole('textbox', { name: 'Search all columns' }).first().fill(detail.row_key.split('|')[1]!)
  const row = page.locator(`[data-testid=batch-row][data-row-key="${detail.row_key}"]`)
  await row.getByRole('img', { name: 'Inbound check: amber' }).click() // the dot itself, not the row
  await expect(page.getByTestId('batch-drawer')).toHaveCount(0)
  const win = page.getByTestId('inbound-window')
  await expect(win.getByTestId('inbound-result')).toContainText('Completed (Resolved)')
  await expect(win.getByRole('img', { name: 'Inbound check: amber' })).toBeVisible()
})

test('F19-AC-05: B1042 Sample Data lists its sample with counts per status, and a click on the Sample ID copies it', async ({ page, request, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  const key = await rowKeyOf(request, 'B1042')
  const detail = (await (await request.get(`/api/rows/${encodeURIComponent(key)}`, { headers: alex })).json()) as { samples: { sample_id: string; status: string }[] }
  expect(detail.samples).toHaveLength(1) // the story batch keeps one sample (OQ-110)
  // A sample is "received" until the LIMS approves it (the live-update test may already have done that).
  const pill = detail.samples[0]!.status === 'approved' ? 'Approved' : detail.samples[0]!.status === 'rejected' ? 'Rejected' : 'Received'
  await page.goto('/overview?q=B1042')
  const row = page.locator(`[data-testid=batch-row][data-row-key="${key}"]`)
  await row.getByTestId('sample-badge').click() // the sample-count badge in the Stage cell
  const win = page.getByTestId('samples-window')
  await expect(win.getByRole('heading', { name: /^Sample Data — B1042 \(1 sample\)$/ })).toBeVisible()
  await expect(win.getByText('LIMS sample records for this batch. Click a Sample ID to copy it.')).toBeVisible()
  await expect(win.getByRole('button', { name: 'All (1)' })).toBeVisible()
  await expect(win.getByRole('button', { name: `${pill} (1)` })).toBeVisible()
  const id = win.getByTestId('window-row').first().getByRole('button')
  const text = (await id.textContent())!
  expect(text).toBe(detail.samples[0]!.sample_id)
  await id.click()
  await expect(page.getByRole('status').filter({ hasText: 'Copied' })).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(text)
})
