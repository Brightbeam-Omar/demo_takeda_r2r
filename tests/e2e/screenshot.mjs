// Saves the Overview at 1440x900 to docs/screenshots/overview.png (npm run screenshot, stack running).
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await page.goto(process.env.FRONTEND_URL ?? 'http://localhost:5173/overview')
await page.waitForSelector('[data-testid=batch-row]')
await page.waitForTimeout(500)
await page.screenshot({ path: new URL('overview.png', out).pathname })
await browser.close()
