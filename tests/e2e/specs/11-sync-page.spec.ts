import { execSync } from 'node:child_process'
import { expect, test } from '@playwright/test'
import { REPO_ROOT } from '../helpers'

test('F11-AC-05 / F21: after a pipeline run the Webhook page shows a new event reach done and Sync Status a new run', async ({ page }) => {
  await page.goto('/admin/webhooks')
  await expect(page.getByTestId('sync-event').first()).toBeVisible()
  const before = Number(await page.getByTestId('sync-event').first().getAttribute('data-row-key'))

  execSync('make pipeline', { cwd: REPO_ROOT, stdio: 'pipe' })

  // The page polls by itself. Record the new event's statuses as they appear: they may only move forward.
  const order = ['pending', 'claimed', 'done']
  const seen: string[] = []
  await expect
    .poll(
      async () => {
        const newest = page.getByTestId('sync-event').first()
        const id = Number(await newest.getAttribute('data-row-key'))
        if (id <= before) return 'waiting'
        const status = (await newest.getByTestId('event-status').innerText()).trim()
        if (seen.at(-1) !== status) seen.push(status)
        return status
      },
      { timeout: 90_000, intervals: [500] },
    )
    .toBe('done')
  expect(seen.map((status) => order.indexOf(status))).toEqual([...seen.map((status) => order.indexOf(status))].sort())
  await expect(page.getByTestId('sync-event').first()).toContainText('webhook')

  await page.goto('/admin/sync')
  const newest = page.getByTestId('run-row').first()
  await expect(newest.getByTestId('run-status')).toHaveText('OK')
  await expect(newest.getByRole('link', { name: /Open run .* in Dagster/ })).toHaveAttribute('href', /localhost:3001\/runs\//)
})
