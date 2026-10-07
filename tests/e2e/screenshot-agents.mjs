// Saves the F12 screenshots at 1440x900 to docs/screenshots/ (npm run screenshots:agents).
// The stack must be freshly seeded (`make seed`) and `services/agents/recordings/air_gap/` must exist: the script
// empties the agent tables, runs the agent as Alex from the Insights window, and shoots the result.
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { chromium } from '@playwright/test'

const base = process.env.FRONTEND_URL ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url)
mkdirSync(out, { recursive: true })
const file = (name) => new URL(name, out).pathname

const compose = ['compose', ...(process.env.COMPOSE_PROJECT_NAME ? ['-p', process.env.COMPOSE_PROJECT_NAME] : [])]
const sql =
  "TRUNCATE action_log, proposal, agent_trace RESTART IDENTITY; ALTER SEQUENCE agent_trace_seq RESTART; " +
  "DELETE FROM audit_event WHERE action IN ('agent_run','proposal_created','proposal_approved','proposal_executed'," +
  "'proposal_rejected','proposal_rejected_by_validator','forbidden');"
execFileSync('docker', [...compose, 'exec', '-T', 'postgres', 'psql', '-U', process.env.POSTGRES_USER ?? 'r2r', '-d', 'app', '-c', sql], { stdio: 'pipe' })

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
await context.addInitScript(() => sessionStorage.setItem('r2r.persona', 'alex'))
const page = await context.newPage()

// Run from the Insights window, then show the Proposal column.
await page.goto(`${base}/overview`)
await page.getByTestId('insights-banner').getByRole('button').click()
await page.getByRole('button', { name: 'Run air-gap agent' }).click()
await page.getByTestId('run-result').waitFor()
await page.getByTestId('proposal-link').first().waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: file('insights-proposals.png') })

// The inbox.
await page.goto(`${base}/agents`)
await page.getByTestId('proposal-row').first().waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: file('agents-inbox.png') })

// B5003's proposal: evidence and the V1-V6 checklist (the evidence table and the checklist both in view).
await page.getByTestId('proposal-row').filter({ hasText: 'B5003' }).click()
await page.getByTestId('validator-checklist').waitFor()
await page.getByTestId('evidence-table').scrollIntoViewIfNeeded()
await page.waitForTimeout(400)
await page.screenshot({ path: file('proposal-b5003.png'), fullPage: true })

// Its trace (after an approval, so the whole path to the action is on the page).
await page.getByRole('button', { name: 'Approve' }).click()
await page.getByTestId('executed-preview').waitFor()
await page.getByTestId('view-trace').click()
await page.getByTestId('trace-step').first().waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: file('trace-b5003.png'), fullPage: true })

await browser.close()
