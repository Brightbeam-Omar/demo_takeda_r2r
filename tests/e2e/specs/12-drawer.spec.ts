import { expect, test } from '@playwright/test'
import { clickRow, rowKeyOf } from '../helpers'

test('F19-AC-01: the B4410 drawer shows five lots under Other lots with the current one marked, a blue current stage and total days against the target; closing puts B4410 into the Batch filter', async ({ page }) => {
  await page.goto('/overview?q=B4410')
  // The table shows in-flight lots only (F17-FR-10): the open re-evaluation, the one still in sampling. The four
  // released lots of the batch appear in the drawer.
  await expect(page.getByTestId('batch-row')).toHaveCount(1)
  await clickRow(page.getByTestId('batch-row').filter({ hasText: 'Sampling' }))

  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer).toBeVisible()
  const lots = drawer.getByTestId('lot-item')
  await expect(lots).toHaveCount(5)
  await expect(lots.nth(0)).toContainText('Initial')
  await expect(lots.nth(1)).toContainText('Re-eval 1')
  await expect(lots.nth(3)).toContainText('Re-eval 3')
  await expect(lots.nth(4)).toContainText('(current)')
  await expect(lots.nth(4).getByRole('button')).toBeDisabled()
  await expect(drawer.getByTestId('stage-timeline').locator('[data-tone=blue]')).toHaveCount(1) // the current stage
  await expect(drawer.getByTestId('total-days')).toContainText(/\d+d \/ 45d target/)
  await expect(drawer.getByTestId('history-summary')).toContainText('Excipient 021')

  // Another lot opens its own drawer content (the same drawer), and the current mark moves.
  await lots.nth(0).click()
  await expect(drawer.getByRole('heading', { level: 2 })).toContainText('RM10052')
  await expect(drawer.getByTestId('lot-item').nth(0)).toContainText('(current)')

  // Closing the drawer puts the batch number into the table's Batch filter box.
  await drawer.getByRole('button', { name: 'Close drawer' }).click()
  await expect(drawer).toBeHidden()
  await expect(page).toHaveURL(/q=B4410/)
  await expect(page).not.toHaveURL(/row=/)
  await expect(page.getByLabel('Filter Batch')).toHaveValue('B4410')
})

test('F19-FR-01: the drawer is non-modal: the table beside it stays interactive, a row click swaps it, and the persona switcher works', async ({ page }) => {
  await page.goto('/overview')
  const rows = page.getByTestId('batch-row')
  await expect(rows.first()).toBeVisible()
  await clickRow(rows.nth(0))
  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer).toBeVisible()
  const first = await drawer.getByRole('heading', { level: 2 }).textContent()

  await clickRow(rows.nth(1)) // no close in between
  await expect(drawer.getByRole('heading', { level: 2 })).not.toHaveText(first ?? '')
  await expect(drawer).toBeVisible()

  // Table and drawer sit side by side: the drawer is to the right and does not cover the table's left edge.
  const table = await page.getByRole('grid', { name: 'Pipeline — Exceptions First' }).boundingBox()
  const box = await drawer.boundingBox()
  expect(box!.width).toBeGreaterThanOrEqual(520)
  expect(table!.x + 100).toBeLessThan(box!.x)

  // The persona switcher works while the drawer is open.
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('quinn')
  await expect(page.getByTestId('user-chip')).toHaveText('Quinn · QC Lead')
  await expect(drawer).toBeVisible()
  await page.getByRole('combobox', { name: 'Persona' }).selectOption('pat')
  await expect(page.getByTestId('user-chip')).toHaveText('Pat · Planner')
})

test('F19-AC-03: the B3150 drawer shows Red and one open deviation, and its Open ↗ link opens the Quality window with a Major card', async ({ page }) => {
  await page.goto('/overview?q=B3150')
  const row = page.getByTestId('batch-row').first()
  await expect(row.getByRole('img', { name: 'Deviations: red' })).toBeVisible()
  await clickRow(row)
  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer.getByTestId('quality-summary')).toContainText('Red')
  await expect(drawer.getByTestId('quality-summary')).toContainText('1 open deviation')

  await drawer.getByRole('button', { name: 'Open Quality window' }).click()
  const win = page.getByTestId('quality-window')
  await expect(win.getByTestId('quality-rating')).toContainText('Red, 1 open deviation')
  await expect(win.getByRole('tab', { name: 'Open Deviations (1)' })).toBeVisible()
  const card = win.getByTestId('deviation-card')
  await expect(card).toHaveCount(1)
  await expect(card.getByTestId('severity-badge')).toHaveText('Major')
  await expect(card).toContainText('Causal Factor')
  await win.getByRole('button', { name: 'Minor' }).click()
  await expect(card).toHaveCount(0) // the severity pills filter
  await win.getByRole('button', { name: 'ALL', exact: true }).click()
  await expect(card).toHaveCount(1)

  await page.keyboard.press('Escape') // closing the window leaves the drawer open
  await expect(win).toBeHidden()
  await expect(drawer).toBeVisible()
})

test('F19-AC-03: a green batch with a linked change control shows Changes (1) in the Quality window', async ({ page, request }) => {
  const { rows } = (await (await request.get('/api/overview', { headers: { 'X-Demo-User': 'alex' } })).json()) as {
    rows: { row_key: string; deviation_light: string }[]
  }
  let found: { key: string; cc: string } | null = null
  for (const row of rows.filter((r) => r.deviation_light === 'green')) {
    const detail = (await (await request.get(`/api/rows/${encodeURIComponent(row.row_key)}`, { headers: { 'X-Demo-User': 'alex' } })).json()) as { changes: { cc_no: string }[] }
    if (detail.changes.length > 0) {
      found = { key: row.row_key, cc: detail.changes[0]!.cc_no }
      break
    }
  }
  expect(found, 'a green in-flight batch with a change control').not.toBeNull()
  await page.goto(`/overview?win=quality&row=${encodeURIComponent(found!.key)}`)
  const win = page.getByTestId('quality-window')
  await expect(win.getByTestId('quality-rating')).toContainText('Green')
  await win.getByRole('tab', { name: /^Changes \(\d+\)$/ }).click()
  await expect(win.getByTestId('change-card').first()).toContainText(found!.cc)
})

test('F11-FR-07: ?row= opens the drawer even when the table filter hides that row; a missing batch says so', async ({ page, request }) => {
  const key = await rowKeyOf(request, 'B2077')
  await page.goto('/overview?q=B4410&row=' + encodeURIComponent(key))
  const drawer = page.getByTestId('batch-drawer')
  await expect(drawer).toContainText('B2077')
  await expect(page.locator('[data-testid=batch-row][data-row-key^="RM10031|B2077|"]')).toHaveCount(0)
  await page.goto('/overview?row=' + encodeURIComponent('NOPE|B0|0'))
  await expect(page.getByTestId('batch-drawer')).toContainText('Batch not found')
})
