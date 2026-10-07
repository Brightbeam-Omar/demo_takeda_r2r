import { mkdirSync, renameSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test, type BrowserContext, type Page } from '@playwright/test'
import { asPersona, beat, DAGSTER_URL, openRow, REPO_ROOT, runStep } from '../helpers'

// F14-FR-01 / AC-02: the presenter's path, acts 2, 3, 5 and 6 of 01-product-overview §6, clicked the way the
// Presenter clicks it, on the parity UI. It needs the demo-start state (`make demo-reset`) and the recorded model
// answers (`LLM_PROVIDER=replay`), and it changes that state, so it runs first and alone (OQ-162).
// The time budget (6 minutes) excludes the reset, which `make e2e` runs before this spec.
test.describe.configure({ mode: 'serial' })
test.setTimeout(6 * 60_000)

const started = Date.now()
const VIDEO_DIR = resolve(REPO_ROOT, 'artifacts/video')
const SIZE = { width: 1440, height: 900 }

// One browser page for the whole run, as one presenter sitting at one screen: it is also what makes the backup video
// a single continuous recording (`make record-video`, F14-FR-07, OQ-164).
let context: BrowserContext
let page: Page
const external: string[] = [] // requests the browser tried to make beyond this machine (F14-AC-01: offline)

test.beforeAll(async ({ browser, baseURL }) => {
  const recording = process.env.RECORD_VIDEO === '1'
  if (recording) rmSync(resolve(VIDEO_DIR, 'raw'), { recursive: true, force: true })
  context = await browser.newContext({
    baseURL,
    viewport: SIZE,
    recordVideo: recording ? { dir: resolve(VIDEO_DIR, 'raw'), size: SIZE } : undefined,
  })
  // The demo runs with the Wi-Fi off: anything that is not this machine is refused and counted.
  await context.route(
    (url) => !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname),
    (route) => {
      external.push(route.request().url())
      return route.abort()
    },
  )
  page = await context.newPage()
})

test.afterEach(async ({}, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) await page.screenshot({ path: testInfo.outputPath('failure.png') })
})

test.afterAll(async () => {
  const video = page.video()
  await context.close() // finishes the recording
  if (video) {
    mkdirSync(VIDEO_DIR, { recursive: true })
    renameSync(await video.path(), resolve(VIDEO_DIR, 'run-of-show.webm'))
    rmSync(resolve(VIDEO_DIR, 'raw'), { recursive: true, force: true })
  }
})

test('act 2 · Monday morning: exceptions first, and the persona decides what you can do', async () => {
  const opened = Date.now()
  await page.goto('/overview')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
  await expect(page.getByTestId('batch-row').first()).toBeVisible({ timeout: 2_000 }) // "loads in < 2 s"
  expect(Date.now() - opened).toBeLessThan(4_000)
  await expect(page.getByTestId('insights-banner')).toContainText('LIMS–SAP Insights (4 batches)') // exceptions first
  await beat(page)

  await asPersona(page, 'sam')
  await expect(page.getByTestId('user-chip')).toHaveText('Sam · Viewer')
  const pencil = page.getByRole('button', { name: 'Edit need-by' }).first()
  await expect(pencil).toBeDisabled()
  await expect(pencil).toHaveAttribute('title', 'Read-only role')
  await beat(page)

  await asPersona(page, 'pat')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
  await expect(pencil).toBeEnabled()
  await beat(page)
})

test('act 3 · under the hood: one LIMS approval travels the real path to the screen, and Explain traces a number', async () => {
  await page.goto('/overview?q=B1042')
  const row = openRow(page, 'B1042')
  await expect(row).toContainText('QCL Testing')
  await beat(page)

  // Demo Controls (admin): the step goes through LIMS, the pipeline and the sync, with live progress.
  await asPersona(page, 'admin')
  await page.getByRole('link', { name: 'Demo Controls' }).click()
  const step = page.locator('[data-step="lims-approve-B1042"]')
  await expect(step.getByTestId('precondition-light')).toHaveAttribute('data-state', 'met')
  const clicked = Date.now()
  await runStep(page, 'lims-approve-B1042', 90_000)
  expect(Date.now() - clicked, 'ms from the click to a synced screen').toBeLessThan(90_000)
  await expect(page.getByTestId('progress-line').filter({ hasText: 'LIMS: approve the sample' })).toBeVisible()
  // F14-FR-09: it cannot be run twice, and the reason is the tooltip.
  await expect(step.getByTestId('precondition-light')).toHaveAttribute('data-state', 'unmet')
  await expect(step.getByRole('button', { name: /^Run / })).toBeDisabled()
  await expect(step.getByTestId('run-reason')).toHaveAttribute('title', /already been approved in LIMS/)
  await beat(page)

  // The hops, one by one: the webhook row, then the pipeline run in Dagster.
  await page.getByRole('link', { name: 'Webhook Sync Status' }).click()
  await expect(page.getByTestId('sync-event').first().getByTestId('event-status')).toHaveText('done')
  await beat(page)
  await page.getByRole('link', { name: /^Sync Status$/ }).click()
  const run = page.getByTestId('run-row').first()
  await expect(run.getByTestId('run-status')).toHaveText('OK')
  const dagster = run.getByRole('link', { name: /Open run .* in Dagster/ })
  await expect(dagster).toHaveAttribute('href', new RegExp(`${DAGSTER_URL}/runs/`))
  const href = (await dagster.getAttribute('href')) as string
  expect((await page.request.get(href)).ok(), 'the run page exists in Dagster').toBe(true)
  await beat(page)

  // The batch moved, highlighted, without a reload of the page by hand.
  await page.goto('/overview?q=B1042')
  await expect(openRow(page, 'B1042')).toContainText('QA Release')
  await beat(page)

  // Explain this number: the ⓘ on a metric card and on a row.
  await page.goto('/overview')
  const card = page.getByTestId('metric-M3')
  await card.getByRole('button', { name: 'Explain M3' }).click()
  const popover = page.getByTestId('explain-popover')
  await expect(popover).toContainText('M3 · Sampling On-Time')
  await expect(popover).toContainText('Pipeline run')
  await beat(page)
  await page.keyboard.press('Escape')
  const first = page.getByTestId('batch-row').first()
  await first.hover()
  await first.getByRole('button', { name: 'Explain stage' }).click()
  await expect(page.getByTestId('explain-popover')).toContainText(/Rule R-/)
  await beat(page)
  await page.keyboard.press('Escape')
})

test('act 5 · human judgement: the planner pulls B2077 forward a week; the plan, the colour and the audit log follow', async () => {
  await page.goto('/overview?q=B2077')
  await asPersona(page, 'pat') // back from Admin
  const row = openRow(page, 'B2077')
  await expect(row.getByTestId('expected-cell')).toContainText('15 Oct')
  await row.getByRole('button', { name: 'Edit need-by' }).click()
  const win = page.getByTestId('needby-window')
  await expect(win.getByTestId('system-date-box')).toHaveText('3 Dec 2026')
  await win.getByLabel('New Adjusted Date').fill('2026-11-26')
  await expect(win.getByTestId('needby-delta')).toHaveText('−7d (pulled forward)')
  await win.getByLabel('Reason for Change').selectOption('CAMPAIGN_PULLED_FORWARD')
  const deadlines = win.getByTestId('preview-deadlines')
  await expect(deadlines).toContainText('Sampling: 14 Oct 2026')
  await expect(deadlines).toContainText('QCL Testing: 20 Nov 2026')
  await expect(deadlines).toContainText('QA Release: 26 Nov 2026')
  await beat(page)
  await win.getByRole('button', { name: 'Save' }).click()
  await expect(win).toBeHidden()

  await expect(row.getByTestId('adjusted-need-by')).toContainText('26 Nov 2026')
  await expect(row.getByTestId('expected-cell')).toContainText('14 Oct') // 15 Oct → 14 Oct
  await expect(row.getByTestId('status-cell')).toHaveAttribute('data-status', 'due') // green → amber
  await beat(page)

  await page.getByRole('link', { name: 'Audit Log' }).click()
  const entry = page.locator('[data-testid=audit-entry][data-action=need_by_set]').first()
  await expect(entry).toContainText('pat')
  await expect(entry).toContainText('B2077')
  await beat(page)
})

test('act 6 · the harness: the agent proposes a ticket with evidence, the validator passes, QA approves, the trace shows it', async () => {
  await page.goto('/overview')
  await asPersona(page, 'alex')
  await page.getByTestId('insights-banner').getByRole('button').click()
  await page.getByRole('button', { name: 'Run air-gap agent' }).click()
  await expect(page.getByTestId('run-result')).toContainText('4 proposals created.')
  const rows = page.getByTestId('window-row')
  await expect(rows.filter({ hasText: 'Pending approval' })).toHaveCount(4)
  await beat(page)

  await rows.filter({ hasText: 'B5003' }).getByTestId('proposal-link').click()
  await expect(page.getByRole('heading', { name: /Air-gap ticket for B5003/ })).toBeVisible()
  await expect(page.getByTestId('evidence-table')).toBeVisible()
  await expect(page.getByTestId('evidence-row').locator('[data-verified]').first()).toHaveAttribute('data-verified', 'true')
  for (const id of ['V1', 'V2', 'V3', 'V4', 'V5', 'V6']) await expect(page.getByTestId(`rule-${id}`)).toHaveAttribute('data-passed', 'true')
  // F14-FR-10: times read as site time, never as ISO text.
  await expect(page.getByTestId('evidence-table')).toContainText(/\d{1,2} [A-Z][a-z]{2} 2026 \d{2}:\d{2}/)
  expect(await page.getByTestId('evidence-table').innerText()).not.toMatch(/\dT\d{2}:/)
  expect(await page.getByTestId('draft').innerText()).not.toMatch(/\dT\d{2}:/)
  await beat(page)

  // Governance: the planner may not approve, the QA lead may.
  await asPersona(page, 'pat')
  await expect(page.getByRole('button', { name: 'Approve' })).toBeDisabled()
  await asPersona(page, 'alex')
  await page.getByRole('button', { name: 'Approve' }).click()
  const preview = page.getByTestId('executed-preview')
  await expect(preview).toBeVisible()
  await expect(preview.getByTestId('delivery')).toHaveText('Sent to outbox (demo)')
  await expect(page.getByTestId('decided-line')).toContainText('Approved by alex')
  await beat(page)

  await page.getByTestId('view-trace').click()
  await expect(page).toHaveURL(/\/agents\/traces\/TR-\d+$/)
  await expect(page.getByTestId('trace-step').first()).toBeVisible()
  const kinds = await page.getByTestId('trace-step').evaluateAll((items) => items.map((i) => i.getAttribute('data-step-type')))
  expect(kinds[0]).toBe('input')
  expect(kinds.filter((k) => k === 'tool_call').length).toBeGreaterThanOrEqual(3)
  await expect(page.getByTestId('trace-provider')).toContainText('replay')
  await beat(page)
})

test('offline · the browser asked for nothing beyond this machine', () => {
  expect(external).toEqual([])
})

test.afterAll(() => {
  const minutes = (Date.now() - started) / 60_000
  console.log(`run-of-show: ${minutes.toFixed(1)} min (budget 6 min, F14-AC-02)`)
  expect(minutes).toBeLessThan(6)
})
