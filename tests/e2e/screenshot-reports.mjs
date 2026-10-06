// Saves the F20 tab screenshots at 1440x900 to docs/screenshots/ (npm run screenshots:reports; stack running, freshly seeded).
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })
const file = (name) => new URL(name, out).pathname

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

const tabs = [
  ['summary', 'report-summary', 'reports-summary.png'],
  ['sla', 'sla-chart', 'reports-sla.png'],
  ['trends', 'stage-chart', 'reports-trends.png'],
  ['late', 'late-row', 'reports-late.png'],
  ['release-rate', 'release-chart', 'reports-release-rate.png'],
  ['adherence', 'adherence-chart', 'reports-adherence.png'],
]
for (const [tab, ready, name] of tabs) {
  await page.goto(`${base}/reports?tab=${tab}`)
  await page.getByTestId(ready).first().waitFor()
  await page.waitForTimeout(600) // the charts draw once the container has a size
  await page.screenshot({ path: file(name) })
}
await browser.close()
console.log('saved the reports screenshots')
