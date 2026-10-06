import { expect, test } from '@playwright/test'

// F20 acceptance tests on the live stack (make up, make seed). Figures are read from the API, never hard-coded,
// except the ones the spec fixes (week 41, the 468 open rows, the 90% line).
const pat = { 'X-Demo-User': 'pat' }
const quinn = { 'X-Demo-User': 'quinn' }

interface Summary {
  year: number
  release: { released: number; annual_target: number; prorata_target: number; pct_of_prorata: number; coverage_weeks: number }
  adherence: { on_time: number; late: number; excluded: number; pct: string; rag: string }
  expedite: { on_time: number; late: number; expedited: number }
}

async function summary(request: import('@playwright/test').APIRequestContext): Promise<Summary> {
  return (await (await request.get('/api/reports/summary', { headers: pat })).json()) as Summary
}

test('F20-AC-01: Executive Summary shows the year-to-date release rate with the pro-rata marker', async ({ page, request }) => {
  const data = await summary(request)
  await page.goto('/reports')
  const card = page.getByTestId('card-release')
  await expect(card.getByTestId('card-release-figure')).toHaveText(`${data.release.released} / ${data.release.annual_target}`)
  await expect(card.getByTestId('card-release-counts')).toContainText(`${data.release.pct_of_prorata}% of pro-rata target`)
  const marker = Math.min(100, (data.release.prorata_target / data.release.annual_target) * 100)
  await expect(card.getByTestId('card-release-marker')).toHaveAttribute('style', new RegExp(`left: ${Math.floor(marker)}(\\.\\d+)?%`))
  await expect(page.getByTestId('card-expedite')).toContainText('does not penalise the standard SLA')
  await expect(page.getByTestId('reports-coverage')).toContainText('Coverage from')
  await expect(page.getByTestId('reports-na-banner')).toContainText('M1, M2, M4, M5 show N/A')
})

test('F20-AC-02: SLA Performance shows week 41 with M3 green, M6 amber, M7 red and the 90% dashed line', async ({ page }) => {
  await page.goto('/reports?tab=sla')
  await expect(page.getByText(/last complete week \(week 41\)/)).toBeVisible()
  const chart = page.getByTestId('sla-chart')
  await expect(chart.getByText('94%', { exact: true })).toBeVisible()
  await expect(chart.getByText('84%', { exact: true })).toBeVisible()
  await expect(chart.getByText('69%', { exact: true })).toBeVisible()
  await expect(chart.locator('path[fill="#16A34A"]')).toHaveCount(1) // M3
  await expect(chart.locator('path[fill="#D97706"]')).toHaveCount(1) // M6
  await expect(chart.locator('path[fill="#DC2626"]')).toHaveCount(1) // M7
  await expect(chart.locator('line[stroke-dasharray="6 4"]')).toHaveCount(1)
  await expect(page.getByText('Dashed line: 90% target')).toBeVisible()
  await expect(page.getByTestId('sla-na')).toContainText('M1: N/A')
})

test('F20-AC-03: Trends weekly shows four complete weeks and the current one, with the trend in points', async ({ page }) => {
  await page.goto('/reports?tab=trends')
  const table = page.getByTestId('trend-table')
  await expect(table.getByRole('columnheader')).toHaveText(['Metric', 'Wk 38', 'Wk 39', 'Wk 40', 'Wk 41', 'Wk 42to date', 'Trend'])
  await expect(page.getByTestId('trend-M3')).toHaveText('▲ +12.6 pp')
  await expect(page.getByTestId('trend-M7')).toHaveText('▼ −14.1 pp')
  await expect(page.getByTestId('trend-row-M3').locator('td[data-rag=green]')).toHaveCount(1) // week 41 is the only one at 90%
  await page.getByRole('button', { name: 'Monthly' }).click()
  await expect(table.getByRole('columnheader')).toHaveText(['Metric', 'Jul 2026', 'Aug 2026', 'Sep 2026', 'Oct 2026to date', 'Trend'])
})

test('F20-AC-04: Pipeline Stage Trends: the latest day stacks to the open rows that have a stage (468)', async ({ page, request }) => {
  const trends = (await (await request.get('/api/reports/trends?stage_grain=daily', { headers: pat })).json()) as {
    points: { day: string; total: number }[]
  }
  expect(trends.points[trends.points.length - 1]!.total).toBe(468)
  await page.goto('/reports?tab=trends')
  const chart = page.getByTestId('stage-chart')
  await expect(chart.locator('.recharts-bar-rectangle').first()).toBeVisible()
  await expect(chart.getByText('Sampling')).toBeVisible() // the legend names the stages
  await page.getByRole('button', { name: 'Weekly' }).last().click()
  await expect(chart.locator('.recharts-bar-rectangle').first()).toBeVisible()
})

test('F20-AC-05: Late Items matches the Overview late count, and a logged reason shows as the category', async ({ page, request }) => {
  const overview = (await (await request.get('/api/overview', { headers: pat })).json()) as { alerts: { kind: string; count: number }[] }
  const lateCount = overview.alerts.find((alert) => alert.kind === 'late')!.count
  const late = (await (await request.get('/api/reports/late', { headers: pat })).json()) as { count: number; items: { row_key: string; days_over_sla: number }[] }
  expect(late.count).toBe(lateCount)
  const days = late.items.map((item) => item.days_over_sla)
  expect(days).toEqual([...days].sort((a, b) => b - a)) // worst first
  await page.goto('/reports?tab=late')
  await expect(page.getByTestId('late-count')).toHaveText(`${lateCount} late rows, worst first.`)

  const target = late.items[0]!
  const logged = await request.post(`/api/rows/${encodeURIComponent(target.row_key)}/status-log`, {
    headers: quinn,
    data: { status: 'at_risk', team: 'QC Lab', reason_code: 'resource_constraint', comment: `Waiting for an analyst ${Date.now()}` },
  })
  expect(logged.status()).toBe(201)
  await page.reload()
  const [, batch] = target.row_key.split('|')
  await page.getByRole('textbox', { name: 'Search all columns' }).first().fill(batch!)
  await expect(page.getByTestId('late-row').first()).toContainText('Resource constraint')
})

test('F20-AC-06: adherence is amber, and a pull-forward of an unreleased batch changes none of the figures', async ({ request }) => {
  const before = await summary(request)
  expect(before.adherence.rag).toBe('amber')
  expect(Number(before.adherence.pct)).toBeGreaterThanOrEqual(85)
  expect(Number(before.adherence.pct)).toBeLessThan(90)
  expect(before.expedite).toMatchObject({ on_time: 3, expedited: 4 })

  const { rows } = (await (await request.get('/api/overview', { headers: pat })).json()) as { rows: { row_key: string; batch_no: string; system_need_by_locked: string }[] }
  const b2077 = rows.find((row) => row.batch_no === 'B2077')!
  const put = await request.put(`/api/rows/${encodeURIComponent(b2077.row_key)}/need-by`, {
    headers: pat,
    data: { adjusted_date: '2026-11-26', reason_code: 'CAMPAIGN_PULLED_FORWARD', expedite: false },
  })
  expect(put.ok()).toBeTruthy()
  const after = await summary(request)
  expect(after.adherence).toEqual(before.adherence)
  expect(after.release).toEqual(before.release)
  expect(after.expedite).toEqual(before.expedite)
})

test('F20-FR-04: the year selector lists the years with data and the other tabs ignore it', async ({ page }) => {
  await page.goto('/reports')
  const year = page.getByTestId('reports-year')
  await expect(year).toBeEnabled()
  await expect(year.locator('option')).toHaveText(['2026', '2025'])
  await year.selectOption('2025')
  await expect(page).toHaveURL(/year=2025/)
  await page.getByTestId('reports-tab-late').click()
  await expect(year).toBeDisabled()
})

test('F20-FR-06: every tab exports its figures as CSV', async ({ page }) => {
  for (const tab of ['summary', 'sla', 'trends', 'late', 'release-rate', 'adherence']) {
    await page.goto(`/reports?tab=${tab}`)
    const download = page.waitForEvent('download')
    await page.getByTestId('reports-export').click()
    expect((await download).suggestedFilename()).toBe(`${tab}.csv`)
  }
})
