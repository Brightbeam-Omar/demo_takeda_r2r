// Saves the F18 pipeline table at 1440x900 to docs/screenshots/overview-table.png
// (npm run screenshot:table; stack running and seeded): the section title, the tag row, the toolbar and the
// first exception rows, which lead the table.
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await page.goto(`${base}/overview`)
await page.getByTestId('batch-row').first().waitFor()
await page.getByTestId('metric-M3').waitFor()
await page.getByRole('heading', { name: 'Pipeline — Exceptions First' }).evaluate((heading) => heading.scrollIntoView({ block: 'start' }))
await page.waitForTimeout(600)
await page.screenshot({ path: new URL('overview-table.png', out).pathname })
await browser.close()
