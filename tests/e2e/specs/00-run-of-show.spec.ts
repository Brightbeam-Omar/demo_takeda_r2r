import { mkdirSync, renameSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test, type BrowserContext, type Page } from '@playwright/test'
import { asPersona, beat, DAGSTER_URL, enter, installOverlay, openRow, pointAt, presenting, REPO_ROOT, runStep, say, tap } from '../helpers'

// F14-FR-01 / AC-02: the presenter's path, acts 2, 3, 5 and 6 of 01-product-overview §6, clicked the way the
// Presenter clicks it, on the parity UI. It needs the demo-start state (`make demo-reset`) and the recorded model
// answers (`LLM_PROVIDER=replay`), and it changes that state, so it runs first and alone (OQ-162).
// The time budget (6 minutes) excludes the reset, which `make e2e` runs before this spec.
test.describe.configure({ mode: 'serial' })
// CI pace must finish in 6 minutes (F14-AC-02). Presenter pace (the backup video) dwells on every key screen.
test.setTimeout(presenting ? 20 * 60_000 : 6 * 60_000)

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
  await installOverlay(context)
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
  const act = 'Act 2 · Monday morning'
  const opened = Date.now()
  await page.goto('/overview')
  await say(page, act, 'The huddle opens on the Overview, as Pat the planner.')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
  await expect(page.getByTestId('batch-row').first()).toBeVisible({ timeout: 2_000 }) // "loads in < 2 s"
  expect(Date.now() - opened).toBeLessThan(presenting ? 20_000 : 4_000)
  await beat(page)

  await say(page, act, 'Exceptions first: four batches where the lab has approved but the ERP has not caught up.')
  const banner = page.getByTestId('insights-banner')
  await expect(banner).toContainText('LIMS–SAP Insights (4 batches)')
  await pointAt(page, banner)
  await beat(page)

  await say(page, act, 'Every count and percentage is derived from the systems of record, not typed in.')
  await pointAt(page, page.getByTestId('metric-M3'))
  await beat(page)

  await say(page, act, 'Who you are decides what you can do: Sam can only look.')
  await asPersona(page, 'sam')
  await expect(page.getByTestId('user-chip')).toHaveText('Sam · Viewer')
  const pencil = page.getByRole('button', { name: 'Edit need-by' }).first()
  await expect(pencil).toBeDisabled()
  await expect(pencil).toHaveAttribute('title', 'Read-only role')
  await pointAt(page, pencil)
  await beat(page)

  await asPersona(page, 'pat')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
  await expect(pencil).toBeEnabled()
  await beat(page, 4_000)
})

test('act 3 · under the hood: one LIMS approval travels the real path to the screen, and Explain traces a number', async () => {
  const act = 'Act 3 · Under the hood'
  await page.goto('/overview')
  await say(page, act, 'Search for batch B1042: it is in QCL Testing.')
  await enter(page, page.getByRole('searchbox').or(page.getByPlaceholder(/Search/)).first(), 'B1042')
  const row = openRow(page, 'B1042')
  await expect(row).toContainText('QCL Testing')
  await pointAt(page, row)
  await beat(page)

  // Demo Controls (admin): the step goes through LIMS, the pipeline and the sync, with live progress.
  await say(page, act, 'Now play the laboratory: Admin opens Demo Controls.')
  await asPersona(page, 'admin')
  await tap(page, page.getByRole('link', { name: 'Demo Controls' }))
  const step = page.locator('[data-step="lims-approve-B1042"]')
  await expect(step.getByTestId('precondition-light')).toHaveAttribute('data-state', 'met')
  await pointAt(page, step)
  await beat(page)

  await say(page, act, 'Run: the lab approves the sample, the pipeline runs, the app syncs. All real.')
  const clicked = Date.now()
  await runStep(page, 'lims-approve-B1042', 90_000)
  expect(Date.now() - clicked, 'ms from the click to a synced screen').toBeLessThan(90_000)
  await expect(page.getByTestId('progress-line').filter({ hasText: 'LIMS: approve the sample' })).toBeVisible()
  await pointAt(page, page.getByTestId('progress-line').last())
  await beat(page)
  // F14-FR-09: it cannot be run twice, and the reason is the tooltip.
  await say(page, act, 'It cannot be run twice: the button is off, and the tooltip says why.')
  await expect(step.getByTestId('precondition-light')).toHaveAttribute('data-state', 'unmet')
  await expect(step.getByRole('button', { name: /^Run / })).toBeDisabled()
  await expect(step.getByTestId('run-reason')).toHaveAttribute('title', /already been approved in LIMS/)
  await pointAt(page, step.getByTestId('run-reason'))
  await beat(page)

  // The hops, one by one: the webhook row, then the pipeline run in Dagster.
  await say(page, act, 'Hop by hop: the data product signalled the app, and the app picked it up.')
  await tap(page, page.getByRole('link', { name: 'Webhook Sync Status' }))
  await expect(page.getByTestId('sync-event').first().getByTestId('event-status')).toHaveText('done')
  await pointAt(page, page.getByTestId('sync-event').first())
  await beat(page)
  await say(page, act, 'Every pipeline run is listed, with a link to its run page.')
  await tap(page, page.getByRole('link', { name: /^Sync Status$/ }))
  const run = page.getByTestId('run-row').first()
  await expect(run.getByTestId('run-status')).toHaveText('OK')
  const dagster = run.getByRole('link', { name: /Open run .* in Dagster/ })
  await expect(dagster).toHaveAttribute('href', new RegExp(`${DAGSTER_URL}/runs/`))
  const href = (await dagster.getAttribute('href')) as string
  expect((await page.request.get(href)).ok(), 'the run page exists in Dagster').toBe(true)
  await pointAt(page, run)
  await beat(page)

  // The batch moved, highlighted, without a reload of the page by hand.
  await say(page, act, 'And B1042 has moved to QA Release, without anyone retyping a status.')
  await page.goto('/overview?q=B1042')
  await expect(openRow(page, 'B1042')).toContainText('QA Release')
  await pointAt(page, openRow(page, 'B1042'))
  await beat(page)

  // Explain this number: the ⓘ on a metric card and on a row.
  await say(page, act, 'Explain this number: the i on a metric shows its rule, week and contributing batches.')
  await page.goto('/overview')
  await tap(page, page.getByTestId('metric-M3').getByRole('button', { name: 'Explain M3' }))
  const popover = page.getByTestId('explain-popover')
  await expect(popover).toContainText('M3 · Sampling On-Time')
  await expect(popover).toContainText('Pipeline run')
  await beat(page, 6_000)
  await page.keyboard.press('Escape')
  await say(page, act, 'On any row, the i names the rule that put the batch in its stage.')
  const first = page.getByTestId('batch-row').first()
  await first.hover()
  await tap(page, first.getByRole('button', { name: 'Explain stage' }))
  await expect(page.getByTestId('explain-popover')).toContainText(/Rule R-/)
  await beat(page, 6_000)
  await page.keyboard.press('Escape')
})

test('act 5 · human judgement: the planner pulls B2077 forward a week; the plan, the colour and the audit log follow', async () => {
  const act = 'Act 5 · Human judgement'
  await page.goto('/overview?q=B2077')
  await asPersona(page, 'pat') // back from Admin
  const row = openRow(page, 'B2077')
  await say(page, act, 'The campaign for B2077 moves a week earlier. Expected completion today: 15 Oct.')
  await expect(row.getByTestId('expected-cell')).toContainText('15 Oct')
  await pointAt(page, row.getByTestId('expected-cell'))
  await beat(page)

  await tap(page, row.getByRole('button', { name: 'Edit need-by' }))
  const win = page.getByTestId('needby-window')
  await expect(win.getByTestId('system-date-box')).toHaveText('3 Dec 2026')
  await say(page, act, 'The ERP date is 3 Dec. Pat enters the new date: 26 Nov.')
  await enter(page, win.getByLabel('New Adjusted Date'), '2026-11-26')
  await expect(win.getByTestId('needby-delta')).toHaveText('−7d (pulled forward)')
  await pointAt(page, win.getByTestId('needby-delta'))
  await beat(page)
  await say(page, act, 'A date needs a reason.')
  const reason = win.getByLabel('Reason for Change')
  await pointAt(page, reason)
  await reason.selectOption('CAMPAIGN_PULLED_FORWARD')
  const deadlines = win.getByTestId('preview-deadlines')
  await expect(deadlines).toContainText('Sampling: 14 Oct 2026')
  await expect(deadlines).toContainText('QCL Testing: 20 Nov 2026')
  await expect(deadlines).toContainText('QA Release: 26 Nov 2026')
  await say(page, act, 'Before saving, the preview shows how the remaining stages are squeezed.')
  await pointAt(page, deadlines)
  await beat(page, 6_000)
  await tap(page, win.getByRole('button', { name: 'Save' }))
  await expect(win).toBeHidden()

  await say(page, act, 'Saved: the plan date moves from 15 to 14 Oct, and the colour changes from green to amber.')
  await expect(row.getByTestId('adjusted-need-by')).toContainText('26 Nov 2026')
  await expect(row.getByTestId('expected-cell')).toContainText('14 Oct') // 15 Oct → 14 Oct
  await expect(row.getByTestId('status-cell')).toHaveAttribute('data-status', 'due') // green → amber
  await pointAt(page, row.getByTestId('adjusted-need-by'))
  await beat(page)

  await tap(page, page.getByRole('link', { name: 'Audit Log' }))
  await say(page, act, 'And the change is on record: who, when, old value, new value, reason.')
  const entry = page.locator('[data-testid=audit-entry][data-action=need_by_set]').first()
  await expect(entry).toContainText('pat')
  await expect(entry).toContainText('B2077')
  await pointAt(page, entry)
  await beat(page, 6_000)
})

test('act 6 · the harness: the agent proposes a ticket with evidence, the validator passes, QA approves, the trace shows it', async () => {
  const act = 'Act 6 · The agent'
  await page.goto('/overview')
  await asPersona(page, 'alex')
  await say(page, act, 'Alex, the QA release lead, opens the four air gaps.')
  await tap(page, page.getByTestId('insights-banner').getByRole('button'))
  await beat(page, 5_000)
  await say(page, act, 'The agent reads the lab, the ERP and the quality system, and drafts a ticket for each.')
  await tap(page, page.getByRole('button', { name: 'Run air-gap agent' }))
  await expect(page.getByTestId('run-result')).toContainText('4 proposals created.')
  const rows = page.getByTestId('window-row')
  await expect(rows.filter({ hasText: 'Pending approval' })).toHaveCount(4)
  await pointAt(page, page.getByTestId('run-result'))
  await beat(page)

  await say(page, act, 'Open the proposal for B5003.')
  await tap(page, rows.filter({ hasText: 'B5003' }).getByTestId('proposal-link'))
  await expect(page.getByRole('heading', { name: /Air-gap ticket for B5003/ })).toBeVisible()
  await beat(page)
  await say(page, act, 'Every piece of evidence is re-read from its source and ticked as verified.')
  await expect(page.getByTestId('evidence-table')).toBeVisible()
  await expect(page.getByTestId('evidence-row').locator('[data-verified]').first()).toHaveAttribute('data-verified', 'true')
  // F14-FR-10: times read as site time, never as ISO text.
  await expect(page.getByTestId('evidence-table')).toContainText(/\d{1,2} [A-Z][a-z]{2} 2026 \d{2}:\d{2}/)
  expect(await page.getByTestId('evidence-table').innerText()).not.toMatch(/\dT\d{2}:/)
  expect(await page.getByTestId('draft').innerText()).not.toMatch(/\dT\d{2}:/)
  await pointAt(page, page.getByTestId('evidence-table'))
  await beat(page, 6_000)
  await say(page, act, 'Then fixed rules, not another model, check the draft: V1 to V6 all pass.')
  for (const id of ['V1', 'V2', 'V3', 'V4', 'V5', 'V6']) await expect(page.getByTestId(`rule-${id}`)).toHaveAttribute('data-passed', 'true')
  await pointAt(page, page.getByTestId('validator-checklist'))
  await beat(page, 6_000)

  // Governance: the planner may not approve, the QA lead may.
  await say(page, act, 'Governance: the planner cannot approve. Only the right role can.')
  await asPersona(page, 'pat')
  await expect(page.getByRole('button', { name: 'Approve' })).toBeDisabled()
  await pointAt(page, page.getByRole('button', { name: 'Approve' }))
  await beat(page, 5_000)
  await asPersona(page, 'alex')
  await say(page, act, 'Alex approves. A ticket and an email are produced; nothing leaves the building.')
  await tap(page, page.getByRole('button', { name: 'Approve' }))
  const preview = page.getByTestId('executed-preview')
  await expect(preview).toBeVisible()
  await expect(preview.getByTestId('delivery')).toHaveText('Sent to outbox (demo)')
  await expect(page.getByTestId('decided-line')).toContainText('Approved by alex')
  await pointAt(page, preview)
  await beat(page, 6_000)

  await say(page, act, 'The trace: what the agent read, what the model said, the checks, the decision, the action.')
  await tap(page, page.getByTestId('view-trace'))
  await expect(page).toHaveURL(/\/agents\/traces\/TR-\d+$/)
  await expect(page.getByTestId('trace-step').first()).toBeVisible()
  const kinds = await page.getByTestId('trace-step').evaluateAll((items) => items.map((i) => i.getAttribute('data-step-type')))
  expect(kinds[0]).toBe('input')
  expect(kinds.filter((k) => k === 'tool_call').length).toBeGreaterThanOrEqual(3)
  await expect(page.getByTestId('trace-provider')).toContainText('replay')
  await pointAt(page, page.getByTestId('trace-step').first())
  await beat(page, 6_000)
  await pointAt(page, page.getByTestId('trace-totals'))
  await beat(page, 6_000)
})

test('offline · the browser asked for nothing beyond this machine', () => {
  expect(external).toEqual([])
})

test.afterAll(() => {
  const minutes = (Date.now() - started) / 60_000
  console.log(`run-of-show (${presenting ? 'presenter' : 'ci'} pace): ${minutes.toFixed(1)} min`)
  if (!presenting) expect(minutes, 'F14-AC-02: under 6 minutes at CI pace').toBeLessThan(6)
})
