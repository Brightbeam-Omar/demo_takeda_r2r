// Saves docs/screenshots/demo-controls.png at 1440x900 (npm run screenshots:demo; stack running).
// Runs lims-approve-B1042 so the progress log is full, then resets the demo again so it is left clean.
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await page.addInitScript(() => sessionStorage.setItem('r2r.persona', 'admin'))
const done = () => page.locator('[data-testid=run-status][data-status=succeeded]').waitFor({ timeout: 180_000 })

await page.goto(`${base}/admin/demo`)
await page.getByTestId('demo-step').first().waitFor()
await page.getByRole('button', { name: 'Reset demo' }).click()
await page.getByTestId('confirm-dialog').getByRole('button', { name: 'Reset demo' }).click()
await done()
await page.locator('[data-step="lims-approve-B1042"]').getByRole('button', { name: /^Run / }).click()
await page.locator('[data-testid=run-status][data-status=running]').waitFor()
await done()
await page.waitForTimeout(500)
await page.screenshot({ path: new URL('demo-controls.png', out).pathname })

await page.getByRole('button', { name: 'Reset demo' }).click()
await page.getByTestId('confirm-dialog').getByRole('button', { name: 'Reset demo' }).click()
await page.locator('[data-testid=run-status][data-status=running]').waitFor()
await done()
await browser.close()
