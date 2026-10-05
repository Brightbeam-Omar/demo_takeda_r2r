import { execSync } from 'node:child_process'
import { expect, test } from '@playwright/test'
import { REPO_ROOT } from '../helpers'

test('F11-AC-05: after a pipeline run the Sync page shows a new webhook event reach done and the watermark update', async ({ page }) => {
  await page.goto('/sync')
  await expect(page.getByTestId('sync-event').first()).toBeVisible()
  const before = Number(await page.getByTestId('sync-event').first().getAttribute('data-event-id'))
  const runBefore = (await page.getByTestId('last-run').innerText()).slice(0, 8)

  execSync('make pipeline', { cwd: REPO_ROOT, stdio: 'pipe' })

  // The page polls by itself. Record the new event's statuses as they appear: they may only move forward.
  const order = ['pending', 'claimed', 'done']
  const seen: string[] = []
  await expect
    .poll(
      async () => {
        const newest = page.getByTestId('sync-event').first()
        const id = Number(await newest.getAttribute('data-event-id'))
        if (id <= before) return 'waiting'
        const status = (await newest.getByTestId('event-status').innerText()).trim()
        if (seen.at(-1) !== status) seen.push(status)
        return status
      },
      { timeout: 90_000, intervals: [500] },
    )
    .toBe('done')
  expect(seen.map((status) => order.indexOf(status))).toEqual([...seen.map((status) => order.indexOf(status))].sort())
  const newest = page.getByTestId('sync-event').first()
  await expect(newest).toContainText('webhook')
  await expect(newest.getByRole('link')).toHaveAttribute('href', /localhost:3001\/runs\//)
  await expect(page.getByTestId('last-run')).not.toContainText(runBefore)
  await expect(page.getByTestId('watermarks').getByRole('link').first()).toHaveText((await page.getByTestId('last-run').innerText()).slice(0, 8))
})
