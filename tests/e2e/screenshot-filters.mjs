// Saves the F16 Overview at 1440x900 to docs/screenshots/overview-filters-banners.png
// (npm run screenshot:filters; stack running and seeded, B2077 pulled forward so both banners are active).
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await page.goto(`${base}/overview?filters=open&class=drug_substance`)
await page.getByTestId('batch-row').first().waitFor()
await page.getByTestId('adjusted-banner').waitFor()
await page.waitForTimeout(500)
await page.screenshot({ path: new URL('overview-filters-banners.png', out).pathname })
await browser.close()
