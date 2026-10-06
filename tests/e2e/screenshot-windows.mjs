// Saves the F19 drawer and window screenshots at 1440x900 to docs/screenshots/ (npm run screenshot:windows;
// stack running and seeded): drawer-b4410, win-inbound-failed, win-quality-b3150, win-statuslog,
// win-samples-b1042 and win-needby-b2077. Run it right after `make seed` (B1042 is then still unapproved). Nothing is
// saved to the app, except one Status Log entry on B5003 when it has none (so the window is not empty).
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })
const shot = (page, name) => page.screenshot({ path: new URL(name, out).pathname })
const get = async (path, user = 'alex') => (await fetch(`${base}/api${path}`, { headers: { 'X-Demo-User': user } })).json()

const { rows } = await get('/overview')
const keyOf = (batch) => rows.find((row) => row.batch_no === batch).row_key
let failed = null
for (const row of rows) {
  const detail = await get(`/rows/${encodeURIComponent(row.row_key)}`)
  if (detail.inbound_check?.status === 'failed') {
    failed = row.row_key
    break
  }
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
// The page behind a window is loaded before the shot, so the window sits on the real Overview.
const settle = async () => {
  await page.getByTestId('batch-row').first().waitFor()
  await page.getByTestId('metric-M3').waitFor()
  await page.waitForTimeout(500)
}
const open = async (query) => {
  await page.goto(`${base}/overview?${query}`)
  await settle()
}

// The drawer beside the table (AC-01).
await open('q=B4410')
await page.getByTestId('batch-row').first().locator('td').nth(1).click()
await page.getByTestId('lot-item').nth(4).waitFor()
await page.getByRole('heading', { name: 'Pipeline — Exceptions First' }).evaluate((heading) => heading.scrollIntoView({ block: 'start' }))
await page.waitForTimeout(600)
await shot(page, 'drawer-b4410.png')

await open(`win=inbound&row=${encodeURIComponent(failed)}`)
await page.getByTestId('inbound-items').waitFor()
await shot(page, 'win-inbound-failed.png')

await open(`win=quality&row=${encodeURIComponent(keyOf('B3150'))}`)
await page.getByTestId('deviation-card').first().waitFor()
await shot(page, 'win-quality-b3150.png')

const b5003 = keyOf('B5003')
const log = await get(`/rows/${encodeURIComponent(b5003)}/status-log`)
if (log.count === 0) {
  await fetch(`${base}/api/rows/${encodeURIComponent(b5003)}/status-log`, {
    method: 'POST',
    headers: { 'X-Demo-User': 'alex', 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'escalated', team: 'QA', reason_code: 'awaiting_info', comment: 'LIMS result not yet received by the ERP' }),
  })
}
await open(`win=status&row=${encodeURIComponent(b5003)}`)
await page.getByTestId('status-latest').waitFor()
await shot(page, 'win-statuslog.png')

await open(`win=samples&row=${encodeURIComponent(keyOf('B1042'))}`)
await page.getByTestId('window-row').first().waitFor()
await shot(page, 'win-samples-b1042.png')

// Act 5: start from no override (as the e2e spec does), then fill in the date and the reason without saving.
await fetch(`${base}/api/rows/${encodeURIComponent(keyOf('B2077'))}/need-by`, {
  method: 'PUT',
  headers: { 'X-Demo-User': 'pat', 'Content-Type': 'application/json' },
  body: JSON.stringify({ adjusted_date: null, expedite: false }),
})
await open(`win=needby&row=${encodeURIComponent(keyOf('B2077'))}`)
const win = page.getByTestId('needby-window')
await win.getByLabel('New Adjusted Date').fill('2026-11-26')
await win.getByLabel('Reason for Change').selectOption('CAMPAIGN_PULLED_FORWARD')
await win.getByTestId('preview-deadlines').waitFor()
await page.waitForTimeout(400)
await shot(page, 'win-needby-b2077.png')
await browser.close()
