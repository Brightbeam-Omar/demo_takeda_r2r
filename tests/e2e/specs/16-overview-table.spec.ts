import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

// F18 acceptance tests on the live stack (make up, make seed). Dates are the demo clock's, 12 Oct 2026.
const STORY_BATCHES = ['B1042', 'B2077', 'B3150', 'B4410', 'B5003']
const alex = { 'X-Demo-User': 'alex' }
const pat = { 'X-Demo-User': 'pat' }

interface ApiRow {
  row_key: string
  batch_no: string
  stage_key: string
  flags: Record<string, boolean>
  plan: { rag: string | null; days_remaining: number | null; expected_completion: string | null; late: boolean }
}

async function overview(request: APIRequestContext, query = ''): Promise<{ total: number; on_hold_count: number; rows: ApiRow[] }> {
  return (await request.get(`/api/overview${query}`, { headers: alex })).json()
}

/** A plain sampling row that is not one of the story batches, with no hold or COA release on it. */
async function plainSamplingRow(request: APIRequestContext): Promise<ApiRow> {
  const { rows } = await overview(request, '?stage=sampling')
  const row = rows.find((r) => !STORY_BATCHES.includes(r.batch_no) && !r.flags.on_hold && !r.flags.late && !r.flags.release_on_coa && !r.flags.ud_rejected && !r.flags.air_gap)
  if (!row) throw new Error('no plain sampling row in the seed')
  return row
}

async function clear(request: APIRequestContext, rowKey: string) {
  const key = encodeURIComponent(rowKey)
  const flags = ((await (await request.get(`/api/rows/${key}`, { headers: alex })).json()) as { flags: Record<string, boolean> }).flags
  if (flags.manual_hold) await request.post(`/api/rows/${key}/hold`, { data: { on: false, reason: 'test cleanup' }, headers: alex })
  if (flags.release_on_coa) await request.post(`/api/rows/${key}/coa-release`, { data: { on: false, reason: 'test cleanup' }, headers: alex })
}

async function asPersona(page: Page, persona: string) {
  await page.addInitScript((who) => sessionStorage.setItem('r2r.persona', who), persona)
}

const summary = (page: Page) => page.getByTestId('page-summary')
const search = (page: Page) => page.getByRole('textbox', { name: 'Search all columns' }).first()
// textContent, not innerText: the headers are upper-cased by CSS.
const headers = (page: Page) => page.getByRole('columnheader').evaluateAll((cells) => cells.map((cell) => cell.querySelector('button')!.childNodes[0]!.textContent!.trim()))

const DEFAULT_COLUMNS = [
  'Material', 'Campaign', 'Class', 'Batch', 'Lot #', 'Inbound', 'Deviation', 'Location', 'Stage',
  'System Needs-By', 'Adjusted Date', 'SLA Deadline', 'Next Inspection', 'Days In Stage', 'Status', 'Expected Completion',
]

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.removeItem('r2r.columns.overview.pat'))
})

test('F18-AC-01: the default view has the 16 columns in order; Goods Receipt Date joins via Columns and Reset restores 16', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  expect(await headers(page)).toEqual(DEFAULT_COLUMNS)

  await page.getByRole('button', { name: /Columns/ }).first().click()
  const panel = page.getByRole('group', { name: 'Columns' })
  await expect(panel.getByRole('checkbox')).toHaveCount(20)
  await panel.getByRole('checkbox', { name: 'Goods Receipt Date' }).check()
  expect(await headers(page)).toHaveLength(17)
  expect(await headers(page)).toContain('Goods Receipt Date')
  await panel.getByRole('button', { name: 'Reset' }).click()
  expect(await headers(page)).toEqual(DEFAULT_COLUMNS)
})

test('F18-AC-01: at 1440x900 no header or cell of the default view is truncated (text is whole; the table scrolls sideways)', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const clipped = await page.evaluate(() => {
    const out: string[] = []
    const cells = document.querySelectorAll('[role=grid] th, [role=grid] td')
    for (const cell of cells) {
      for (const el of [cell, ...cell.querySelectorAll('*')]) {
        const style = getComputedStyle(el)
        const squeezed = el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0
        if (style.textOverflow === 'ellipsis' || (squeezed && style.overflowX !== 'visible')) {
          out.push(`${el.tagName} "${(el.textContent ?? '').trim().slice(0, 40)}" ${style.textOverflow} ${el.scrollWidth}>${el.clientWidth}`)
        }
        if (squeezed && el.textContent?.trim()) out.push(`overflowing: ${el.tagName} "${el.textContent.trim().slice(0, 40)}" ${el.scrollWidth}>${el.clientWidth}`)
      }
    }
    return out
  })
  expect(clipped).toEqual([])
  // The Location column shows the whole word, not "Onsi…".
  await expect(page.getByTestId('batch-row').first().getByText(/Onsite|3PL/)).toBeVisible()
})

test('F18-AC-02: searching B20 narrows the table, marks matches in Batch and updates the count; × clears it', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const total = (await summary(page).innerText()).match(/of (\d+) lots/)![1]!
  await search(page).fill('B20')
  await expect(page).toHaveURL(/q=B20/)
  await expect.poll(async () => (await summary(page).innerText()).match(/of (\d+) lots/)?.[1]).not.toBe(total)
  const marks = page.getByTestId('batch-row').first().locator('mark')
  await expect(marks.first()).toHaveText(/B20/i)
  const batchCell = page.getByTestId('batch-row').first().getByRole('button', { name: /B20/ })
  await expect(batchCell.locator('mark')).toHaveText('B20')
  await page.getByRole('button', { name: 'Clear search' }).first().click()
  await expect(page.locator('mark')).toHaveCount(0)
  await expect(summary(page)).toContainText(`of ${total} lots`)
})

test('F18-AC-03: Alex places a hold; the row gains ON HOLD, On Hold rises by 1, it sorts into the exceptions and the audit log has hold_placed', async ({ page, request }) => {
  await asPersona(page, 'alex')
  const target = await plainSamplingRow(request)
  const before = await overview(request)
  try {
    await page.goto(`/overview?q=${encodeURIComponent(target.batch_no)}`)
    const row = page.locator(`[data-testid=batch-row][data-row-key="${target.row_key}"]`)
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: /^Actions for/ }).click()
    await page.getByRole('menuitem', { name: '+ Place Hold' }).click()
    await page.getByRole('textbox', { name: 'Reason' }).fill('Awaiting supplier confirmation')
    await page.getByRole('button', { name: 'Confirm' }).click()

    await expect(row.getByText('ON HOLD')).toBeVisible()
    await expect(page.getByTestId('flow-on_hold')).toContainText(String(before.on_hold_count + 1))
    await expect(row).toHaveCSS('background-color', 'rgb(254, 242, 242)')

    const after = await overview(request)
    expect(after.on_hold_count).toBe(before.on_hold_count + 1)
    const exceptions = after.rows.filter((r) => r.plan.late || r.flags.ud_rejected || r.flags.on_hold || r.flags.air_gap)
    const index = after.rows.findIndex((r) => r.row_key === target.row_key)
    expect(index).toBeGreaterThanOrEqual(0)
    expect(index).toBeLessThan(exceptions.length) // inside the exception block at the top
    const audit = (await (await request.get(`/api/audit?action=hold_placed&row_key=${encodeURIComponent(target.row_key)}`, { headers: alex })).json()) as { items: { actor_user_key: string; details: { reason: string } }[] }
    expect(audit.items[0]).toMatchObject({ actor_user_key: 'alex', details: { reason: 'Awaiting supplier confirmation' } })
  } finally {
    await clear(request, target.row_key)
  }
})

test('F18-AC-03: as Sam the Place Hold and Release on COA items are disabled with Read-only role, and a forced call is refused', async ({ page, request }) => {
  await asPersona(page, 'sam')
  const target = await plainSamplingRow(request)
  await page.goto(`/overview?q=${encodeURIComponent(target.batch_no)}`)
  const row = page.locator(`[data-testid=batch-row][data-row-key="${target.row_key}"]`)
  await row.getByRole('button', { name: /^Actions for/ }).click()
  for (const name of ['+ Place Hold', 'Release on COA']) {
    await expect(page.getByRole('menuitem', { name })).toBeDisabled()
    await expect(page.getByRole('menuitem', { name })).toHaveAttribute('title', 'Read-only role')
  }
  const forced = await request.post(`/api/rows/${encodeURIComponent(target.row_key)}/hold`, { data: { on: true, reason: 'forced call' }, headers: { 'X-Demo-User': 'sam' } })
  expect(forced.status()).toBe(403)
})

test('F18-AC-04: Alex releases a sampling row on COA: expected is cycle start + 14 days with the RELEASE ON COA tag; Undo restores the plan', async ({ page, request }) => {
  await asPersona(page, 'alex')
  const target = await plainSamplingRow(request)
  const key = encodeURIComponent(target.row_key)
  const detail = (await (await request.get(`/api/rows/${key}`, { headers: alex })).json()) as { facts: { cycle_start_date: string }; plan: { expected_completion: string } }
  const start = new Date(`${detail.facts.cycle_start_date}T00:00:00Z`)
  start.setUTCDate(start.getUTCDate() + 14)
  const wanted = start.toISOString().slice(0, 10)
  const text = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
  try {
    await page.goto(`/overview?q=${encodeURIComponent(target.batch_no)}`)
    const row = page.locator(`[data-testid=batch-row][data-row-key="${target.row_key}"]`)
    const originalText = await row.getByTestId('expected-cell').innerText()
    await row.getByRole('button', { name: /^Actions for/ }).click()
    await page.getByRole('menuitem', { name: 'Release on COA' }).click()
    await page.getByRole('textbox', { name: 'Reason' }).fill('COA received from supplier')
    await page.getByRole('button', { name: 'Confirm' }).click()
    await expect(row.getByText('RELEASE ON COA')).toBeVisible()
    await expect(row.getByTestId('expected-cell')).toContainText(text(wanted))
    const after = (await (await request.get(`/api/rows/${key}`, { headers: alex })).json()) as { plan: { expected_completion: string } }
    expect(after.plan.expected_completion).toBe(wanted)

    await row.getByRole('button', { name: /^Actions for/ }).click()
    await page.getByRole('menuitem', { name: 'Undo Release on COA' }).click()
    await page.getByRole('textbox', { name: 'Reason' }).fill('COA belonged to another batch')
    await page.getByRole('button', { name: 'Confirm' }).click()
    await expect(row.getByText('RELEASE ON COA')).toBeHidden()
    await expect(row.getByTestId('expected-cell')).toHaveText(originalText)
    expect(((await (await request.get(`/api/rows/${key}`, { headers: alex })).json()) as typeof detail).plan.expected_completion).toBe(detail.plan.expected_completion)
  } finally {
    await clear(request, target.row_key)
  }
})

test('F18-AC-05: Export Sampling Plan and Export QC Testing Queue download as many rows as the stage has under the current filters', async ({ page, request }) => {
  await page.goto('/overview?type=small_molecule')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const rowsOf = async (button: string) => {
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: button }).first().click()])
    const text = await (await import('node:fs/promises')).readFile((await download.path())!, 'utf8')
    return text.trim().split('\n').length - 1
  }
  const sampling = await overview(request, '?type[]=small_molecule&stage=sampling')
  expect(await rowsOf('↓ Export Sampling Plan')).toBe(sampling.total)
  const queue = await overview(request, '?type[]=small_molecule&stage=qc_ship&stage=qc_testing')
  expect(await rowsOf('↓ Export QC Testing Queue')).toBe(queue.total)
  expect(sampling.total).toBeGreaterThan(0)
})

test('F18-AC-05: the Export menu offers This page and All filtered results with the row counts on screen', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  await page.getByRole('button', { name: /↓ Export ▾/ }).first().click()
  await expect(page.getByRole('menuitem', { name: /^This page \(50 rows\)$/ })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: /^All filtered results \(\d+ rows\)$/ })).toBeVisible()
})

test('F18-AC-06: Tab to the table, ↓↓ and Enter open the third row; B toggles its star', async ({ page, request }) => {
  const bookmarks = (await (await request.get('/api/bookmarks', { headers: pat })).json()) as string[]
  for (const key of bookmarks) await request.delete(`/api/bookmarks/${encodeURIComponent(key)}`, { headers: pat })
  try {
    await page.goto('/overview')
    await expect(page.getByTestId('batch-row').first()).toBeVisible()
    const grid = page.getByRole('grid')
    for (let n = 0; n < 80 && !(await grid.evaluate((el) => el === document.activeElement)); n += 1) await page.keyboard.press('Tab')
    await expect(grid).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('ArrowDown')
    const third = page.getByTestId('batch-row').nth(2)
    await expect(third).toHaveAttribute('data-active', 'true')
    const key = (await third.getAttribute('data-row-key'))!

    await page.keyboard.press('b')
    await expect(third.getByRole('button', { name: /^Remove bookmark from / })).toHaveAttribute('aria-pressed', 'true')
    await page.keyboard.press('b')
    await expect(third.getByRole('button', { name: /^Bookmark / })).toHaveAttribute('aria-pressed', 'false')

    await page.keyboard.press('Enter')
    await expect(page.getByTestId('batch-drawer')).toBeVisible()
    await expect(page).toHaveURL(new RegExp(`row=${encodeURIComponent(key).replace(/\|/g, '%7C')}`))
  } finally {
    for (const key of (await (await request.get('/api/bookmarks', { headers: pat })).json()) as string[]) await request.delete(`/api/bookmarks/${encodeURIComponent(key)}`, { headers: pat })
  }
})

test('F18-AC-07: late rows read LATE +Nd with a red Expected Completion (Nd over); an amber row reads DUE IN Nd', async ({ page, request }) => {
  const { rows } = await overview(request)
  const late = rows.find((r) => r.plan.late && r.plan.days_remaining !== null)!
  const amber = rows.find((r) => r.plan.rag === 'amber' && r.plan.days_remaining !== null)
  await page.goto('/overview')
  await expect(page.getByTestId('batch-row').first()).toBeVisible()
  const lateRow = page.getByTestId('batch-row').filter({ has: page.getByTestId('status-cell') }).first()
  const lateRowKey = (await lateRow.getAttribute('data-row-key'))!
  expect(rows.find((r) => r.row_key === lateRowKey)!.plan.late).toBe(true)
  const n = -late.plan.days_remaining!
  expect(n).toBeGreaterThan(0)
  await page.goto(`/overview?q=${encodeURIComponent(late.batch_no)}`)
  const row = page.locator(`[data-testid=batch-row][data-row-key="${late.row_key}"]`)
  await expect(row.getByTestId('status-cell')).toHaveText(`LATE +${n}d`)
  await expect(row.getByTestId('expected-cell')).toContainText(`(${n}d over)`)
  await expect(row.getByTestId('expected-cell')).toHaveClass(/text-red-700/)
  if (amber) {
    await page.goto(`/overview?q=${encodeURIComponent(amber.batch_no)}`)
    await expect(page.locator(`[data-testid=batch-row][data-row-key="${amber.row_key}"]`).getByTestId('status-cell')).toHaveText(`DUE IN ${amber.plan.days_remaining}d`)
  }
})

test('F18-AC-08: Overview p95 is under 300 ms server-side', async ({ request }) => {
  const times: number[] = []
  await request.get('/api/overview', { headers: alex })
  for (let n = 0; n < 40; n += 1) {
    const started = performance.now()
    const response = await request.get('/api/overview', { headers: alex })
    expect(response.ok()).toBe(true)
    await response.body()
    times.push(performance.now() - started)
  }
  times.sort((a, b) => a - b)
  const p95 = times[Math.floor(times.length * 0.95) - 1]!
  console.log(`overview p95 ${p95.toFixed(0)} ms over ${times.length} calls`)
  expect(p95).toBeLessThan(300)
})
