// Saves the F21 screenshots at 1440x900 to docs/screenshots/ (npm run screenshots:admin; stack running, freshly seeded).
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })
const file = (name) => new URL(name, out).pathname

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const shot = async (path, ready, name) => {
  await page.goto(`${base}${path}`)
  await page.getByTestId(ready).first().waitFor()
  await page.waitForTimeout(500)
  await page.screenshot({ path: file(name) })
}

await shot('/admin/sync', 'run-row', 'sync.png')
await shot('/admin/webhooks', 'sync-event', 'webhooks.png')
await shot('/admin/team', 'team-row', 'team.png')
await page.goto(`${base}/admin/schema`)
await page.getByTestId('schema-object').first().waitFor()
await page.getByLabel('Search the schema').fill('pipeline_run')
await page.waitForTimeout(400)
await page.screenshot({ path: file('schema.png') })
await shot('/admin/sla', 'sla-metric', 'sla-config.png')

await browser.close()
