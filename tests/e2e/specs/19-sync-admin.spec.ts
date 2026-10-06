import { execSync } from 'node:child_process'
import { expect, test, type APIRequestContext } from '@playwright/test'
import { REPO_ROOT } from '../helpers'

// F21 acceptance tests on the live stack (make up, make seed). Figures are read from the API, never hard-coded.
const admin = { 'X-Demo-User': 'admin' }

interface Run {
  pipeline_run_id: string
  inserted: number | null
  total: number | null
  skipped: number | null
  status: string
  failed_step: string | null
}

async function runs(request: APIRequestContext): Promise<Run[]> {
  return (await (await request.get('/api/pipeline/runs', { headers: admin })).json()) as Run[]
}

async function persona(page: import('@playwright/test').Page, key: string) {
  await page.getByRole('combobox', { name: 'Persona' }).selectOption(key)
  await expect(page.getByTestId('user-chip')).toBeVisible()
}

test('F21-FR-02: Sync Status lists every pipeline run newest first, and a Run ID opens its steps', async ({ page, request }) => {
  const data = await runs(request)
  expect(data.length).toBeGreaterThan(0)
  await page.goto('/admin/sync')
  await expect(page.getByTestId('page-subtitle')).toContainText('History of every pipeline run — click a Run ID to see per-step detail')
  const rows = page.getByTestId('run-row')
  await expect(rows.first()).toBeVisible()
  await expect(rows.first().getByTestId('run-link')).toHaveText(data[0].pipeline_run_id.slice(0, 8))
  await expect(rows.first()).toContainText(String(data[0].total))
  await rows.first().getByTestId('run-link').click()
  const window = page.getByTestId('run-steps-window')
  await expect(window.getByTestId('run-step')).toHaveCount(5, { timeout: 15_000 }) // up to publish: notify comes with the next run
  await expect(window.getByTestId('run-step').first()).toContainText('setup')
  await page.keyboard.press('Escape')
})

test('F21-AC-01: after two pipeline runs on unchanged data the page shows inserted 0 and skipped = total', async ({ page, request }) => {
  test.setTimeout(300_000)
  execSync('make pipeline', { cwd: REPO_ROOT, stdio: 'pipe' }) // absorbs whatever earlier specs changed
  execSync('make pipeline', { cwd: REPO_ROOT, stdio: 'pipe' })
  await expect.poll(async () => (await runs(request)).length, { timeout: 90_000 }).toBeGreaterThan(1)
  await expect.poll(async () => (await runs(request))[0].inserted, { timeout: 90_000 }).toBe(0)
  const [latest] = await runs(request)
  expect(latest.skipped).toBe(latest.total)
  await page.goto('/admin/sync')
  const cells = page.getByTestId('run-row').first().locator('td')
  await expect(cells.nth(4)).toHaveText('0') // Inserted
  await expect(cells.nth(5)).toHaveText(String(latest.total))
  await expect(cells.nth(6)).toHaveText(String(latest.skipped))
})

test('F21-AC-03: the webhook cards at rest read 0, 0, 0 and Last Drain is under 30 s', async ({ page }) => {
  await page.goto('/admin/webhooks')
  for (const id of ['card-pending', 'card-error', 'card-abandoned', 'card-poll']) {
    await expect(page.getByTestId(`${id}-value`)).toHaveText('0')
    await expect(page.getByTestId(id)).toHaveAttribute('data-tone', 'green')
  }
  await expect(page.getByTestId('card-poll')).toContainText('T2-02')
  await expect(page.getByTestId('card-drain')).toHaveAttribute('data-tone', 'green')
  await expect(page.getByTestId('card-last-webhook')).toContainText('ago')
})

test('F21-FR-04: an event row expands to its drain pass and ages', async ({ page }) => {
  await page.goto('/admin/webhooks')
  const row = page.getByTestId('sync-event').first()
  await expect(row).toBeVisible()
  await row.getByTestId('event-expand').click()
  await expect(page.getByTestId('event-detail')).toContainText('Drain pass')
  await expect(page.getByTestId('event-detail')).toContainText('Claimed')
})

test('F21-AC-04: as Sam both actions are disabled; as Admin Trigger Sync Now asks first, then runs through to done', async ({ page, request }) => {
  await page.goto('/admin/webhooks')
  await persona(page, 'sam')
  await expect(page.getByRole('button', { name: 'Trigger Sync Now' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Drain Queue Now' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Refresh' })).toBeEnabled()

  await persona(page, 'admin')
  const before = Number(await page.getByTestId('sync-event').first().getAttribute('data-row-key'))
  const known = new Set((await runs(request)).map((run) => run.pipeline_run_id))
  await page.getByRole('button', { name: 'Trigger Sync Now' }).click()
  const dialog = page.getByTestId('confirm-dialog')
  await expect(dialog).toContainText("This starts real work that affects everyone's view.")
  await dialog.getByRole('button', { name: 'Start the run' }).click()

  await expect
    .poll(async () => Number(await page.getByTestId('sync-event').first().getAttribute('data-row-key')), { timeout: 240_000, intervals: [1000] })
    .toBeGreaterThan(before)
  await expect(page.getByTestId('sync-event').first().getByTestId('event-status')).toHaveText('done', { timeout: 60_000 })
  const after = await runs(request)
  expect(after.some((run) => !known.has(run.pipeline_run_id))).toBe(true)
  await page.goto('/admin/sync')
  await expect(page.getByTestId('run-row').first().getByTestId('run-link')).toHaveText(after[0].pipeline_run_id.slice(0, 8))
  await persona(page, 'pat')
})

test('F21-AC-05: the late counts of the Team Dashboard add up to the Overview late count', async ({ page, request }) => {
  const overview = (await (await request.get('/api/overview', { headers: admin })).json()) as { alerts: { kind: string; count: number }[] }
  const late = overview.alerts.find((alert) => alert.kind === 'late')?.count ?? -1
  await page.goto('/admin/team')
  await expect(page.getByTestId('team-row').first()).toBeVisible()
  const counts = await page.getByTestId('team-late').allInnerTexts()
  expect(counts.map(Number).reduce((a, b) => a + b, 0)).toBe(late)
  await expect(page.getByTestId('team-total-late')).toHaveText(String(late))
  // A team row opens the Overview filtered to its stages.
  await page.getByRole('link', { name: /View QC Lab in the Overview/ }).click()
  await expect(page).toHaveURL(/stage=qc_ship&stage=qc_testing/)
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
})

test('F21-AC-06: Schema Reference lists every published object', async ({ page, request }) => {
  const schema = (await (await request.get('/api/schema', { headers: admin })).json()) as { objects: { name: string }[] }
  await page.goto('/admin/schema')
  await expect(page.getByTestId('schema-object')).toHaveCount(schema.objects.length)
  expect(schema.objects.map((o) => o.name)).toContain('pipeline_runs_v')
  await page.getByTestId('schema-object').filter({ hasText: 'pipeline_runs_v' }).getByRole('button').click()
  await expect(page.getByTestId('schema-column').filter({ hasText: 'skipped' })).toBeVisible()
})

test('F21-FR-06: SLA Configuration names the profile file; placeholders say Tier 2; old routes redirect', async ({ page }) => {
  await page.goto('/admin/sla')
  await expect(page.getByTestId('sla-note')).toContainText('Configured in the site profile site_a.yaml; changes take effect at the next pipeline run.')
  await expect(page.getByTestId('sla-stage')).not.toHaveCount(0)
  await expect(page.getByTestId('sla-metric')).toHaveCount(7)
  await page.goto('/admin/upload')
  await expect(page.getByTestId('tier-tag')).toContainText('T2-07')
  await page.goto('/audit')
  await expect(page).toHaveURL(/\/admin\/audit$/)
  await page.goto('/sync')
  await expect(page).toHaveURL(/\/admin\/sync$/)
  await expect(page.getByTestId('nav-admin-feedback')).toBeVisible()
})
