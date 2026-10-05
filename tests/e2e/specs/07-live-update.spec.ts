import { execSync } from 'node:child_process'
import { expect, test } from '@playwright/test'
import { envVar, LIMS_URL, REPO_ROOT } from '../helpers'

interface Sample {
  sample_id: string
  status: string
}

test('F10-AC-05: a LIMS approval plus a pipeline run moves B1042 to QA Release, highlighted, within 90 s', async ({ page, request }) => {
  await page.goto('/overview?q=B1042')
  const row = page.locator('[data-testid=batch-row][data-row-key*="|B1042|"]').first()
  await expect(row).toBeVisible()
  await expect(row).toContainText('QCL Testing')

  const samples = (await (await request.get(`${LIMS_URL}/samples?batch_no=B1042`)).json()) as Sample[]
  const latest = [...samples].sort((a, b) => a.sample_id.localeCompare(b.sample_id)).at(-1)
  expect(latest, 'B1042 has a sample').toBeTruthy()

  const started = Date.now()
  const approved = await request.post(`${LIMS_URL}/events/approved`, {
    data: { sample_id: latest!.sample_id },
    headers: { 'X-Scenario-Token': envVar('SCENARIO_TOKEN', 'dev-only-change-me') },
  })
  expect(approved.ok(), await approved.text()).toBe(true)
  // The page keeps polling by itself; nothing below reloads it.
  execSync('make pipeline', { cwd: REPO_ROOT, stdio: 'pipe' })

  await expect(row).toContainText('QA Release', { timeout: 90_000 - (Date.now() - started) })
  await expect(row).toHaveClass(/row-changed/)
  await expect(page.getByRole('status').filter({ hasText: 'Updated just now' })).toBeVisible()
  expect(Date.now() - started, 'seconds from event to screen').toBeLessThan(90_000)
})
