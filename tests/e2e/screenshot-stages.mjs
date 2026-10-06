// Saves the F17 Overview at 1440x900 to docs/screenshots/overview-stages-metrics.png
// (npm run screenshot:stages; stack running and seeded). Sampling, QCL Ship and QCL Testing are selected, so the
// multi-select state, the Clear button, the chips and the showing line are all on screen.
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await page.goto(`${base}/overview?stage=sampling&stage=qc_ship&stage=qc_testing`)
await page.getByTestId('batch-row').first().waitFor()
await page.getByTestId('metric-M3').waitFor()
await page.waitForTimeout(500)
await page.screenshot({ path: new URL('overview-stages-metrics.png', out).pathname })
await browser.close()
