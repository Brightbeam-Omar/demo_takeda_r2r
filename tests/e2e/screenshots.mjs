// Saves the F11 screenshots at 1440x900 to docs/screenshots/ (npm run screenshots; stack running, freshly seeded).
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })
const file = (name) => new URL(name, out).pathname
const key = (value) => encodeURIComponent(value)

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

// B4410: the drawer with the initial lot and its re-evaluations.
await page.goto(`${base}/overview?q=B4410&row=${key('RM10052|B4410|10000795')}`)
await page.getByTestId('lot-item').first().waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: file('drawer-b4410.png') })

// B2077: the need-by editor with the preview, before saving.
await page.goto(`${base}/overview?q=B2077&row=${key('RM10031|B2077|10000782')}`)
await page.getByRole('button', { name: /Edit need-by/ }).click()
const modal = page.getByTestId('need-by-modal')
await modal.getByLabel('Adjusted need-by').fill('2026-11-26')
await modal.getByLabel('Reason').selectOption('CAMPAIGN_PULLED_FORWARD')
await modal.getByTestId('preview-rag').waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: file('needby-preview-b2077.png') })

// M3: the explanation of the last complete week.
await page.goto(`${base}/overview`)
await page.getByTestId('batch-row').first().waitFor()
await page.getByRole('button', { name: 'Explain M3' }).click()
await page.getByTestId('explain-rows').waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: file('explain-m3.png') })

// The Sync page.
await page.goto(`${base}/sync`)
await page.getByTestId('sync-event').first().waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: file('sync.png') })

await browser.close()
