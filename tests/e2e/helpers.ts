import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')

/** Reads one variable from the repo's `.env`, falling back to the process environment. */
export function envVar(name: string, fallback: string): string {
  if (process.env[name]) return process.env[name] as string
  try {
    const line = readFileSync(resolve(REPO_ROOT, '.env'), 'utf8')
      .split('\n')
      .find((entry) => entry.startsWith(`${name}=`))
    if (line) return line.slice(name.length + 1).trim()
  } catch {
    // no .env: use the fallback
  }
  return fallback
}

export const LIMS_URL = `http://localhost:${envVar('LIMS_HOST_PORT', '8102')}`

import type { APIRequestContext } from '@playwright/test'

/** The row key of the in-flight row of a batch, e.g. `RM10031|B2077|10000782` (lot numbers come from the database). */
export async function rowKeyOf(request: APIRequestContext, batch: string): Promise<string> {
  const response = await request.get('/api/overview', { headers: { 'X-Demo-User': 'alex' } })
  const { rows } = (await response.json()) as { rows: { row_key: string; batch_no: string }[] }
  const found = rows.find((row) => row.batch_no === batch)
  if (!found) throw new Error(`no in-flight row for ${batch}`)
  return found.row_key
}

import type { Locator } from '@playwright/test'

/**
 * Opens a row's drawer by clicking a plain text cell (Campaign). The middle of a row can land on a dot, the
 * sample badge or the status bubble, which open their own windows instead (F19-FR-07).
 */
export async function clickRow(row: Locator): Promise<void> {
  await row.locator('td').nth(1).click()
}

import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'

/** True once `make record-agents` has written recordings for the air-gap agent (F12-FR-03). */
export function hasRecordings(): boolean {
  const folder = resolve(REPO_ROOT, 'services/agents/recordings/air_gap')
  return existsSync(folder) && readdirSync(folder).some((name) => name.endsWith('.json'))
}

/**
 * What the demo reset will do to the agent tables (F13, OQ-144), until F13 exists: one TRUNCATE and a restarted
 * trace sequence, through the compose Postgres, so a spec starts from "no proposals".
 */
export function resetAgentState(): void {
  const compose = ['compose', ...(process.env.COMPOSE_PROJECT_NAME ? ['-p', process.env.COMPOSE_PROJECT_NAME] : [])]
  const sql =
    "TRUNCATE action_log, proposal, agent_trace RESTART IDENTITY; ALTER SEQUENCE agent_trace_seq RESTART; " +
    "DELETE FROM audit_event WHERE action IN ('agent_run','proposal_created','proposal_approved','proposal_executed'," +
    "'proposal_rejected','proposal_rejected_by_validator','forbidden');"
  execFileSync('docker', [...compose, 'exec', '-T', 'postgres', 'psql', '-U', envVar('POSTGRES_USER', 'r2r'), '-d', 'app', '-c', sql], {
    cwd: REPO_ROOT,
    stdio: 'pipe',
  })
}

import type { BrowserContext, Page } from '@playwright/test'

/** The Dagster UI a run link opens (F14: act 3 shows the pipeline run there). */
export const DAGSTER_URL = envVar('VITE_DAGSTER_URL', 'http://localhost:3001')

/** `PACE=ci` (default): full speed. `PACE=presenter`: the backup video, paced for a viewer (F14 review, OQ-164). */
export type Pace = 'ci' | 'presenter'
export const PACE: Pace = (() => {
  const value = process.env.PACE ?? 'ci'
  if (value !== 'ci' && value !== 'presenter') throw new Error(`PACE must be "presenter" or "ci", not "${value}"`)
  return value
})()
export const presenting = PACE === 'presenter'

/** How long a key screen stays up in presenter pace: 4 to 6 s (6 s default), so a viewer can read it. */
const DWELL_MS = 6_000

/** A pause on the screen. Full speed (no pause) in CI; `ms` defaults to a key-screen dwell in presenter pace. */
export async function beat(page: Page, ms = DWELL_MS): Promise<void> {
  if (presenting) await page.waitForTimeout(ms)
}

/**
 * Installs the presenter overlay (presenter pace only): a visible mouse pointer that follows the mouse, and a
 * caption bar with the act name and one line of what is happening. Both survive page loads. Playwright's own mouse
 * is invisible in a recording, so the pointer is drawn by the page.
 */
export async function installOverlay(context: BrowserContext): Promise<void> {
  if (!presenting) return
  await context.addInitScript(() => {
    const draw = () => {
      if (document.getElementById('demo-overlay')) return
      const host = document.createElement('div')
      host.id = 'demo-overlay'
      host.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647'
      const pointer = document.createElement('div')
      pointer.style.cssText =
        'position:absolute;width:22px;height:22px;margin:-4px 0 0 -4px;border-radius:50%;' +
        'background:rgba(79,70,229,.35);border:3px solid #4f46e5;box-shadow:0 0 0 2px #fff;transition:transform .08s'
      const bar = document.createElement('div')
      bar.style.cssText =
        'position:absolute;left:50%;bottom:20px;transform:translateX(-50%);max-width:1100px;padding:10px 22px;' +
        'border-radius:10px;background:rgba(15,23,42,.92);color:#fff;font:15px/1.35 system-ui,sans-serif;text-align:center'
      host.append(pointer, bar)
      document.documentElement.append(host)
      const place = (x: number, y: number) => {
        pointer.style.left = `${x}px`
        pointer.style.top = `${y}px`
        sessionStorage.setItem('demo.pointer', JSON.stringify([x, y]))
      }
      const saved = sessionStorage.getItem('demo.pointer')
      if (saved) place(...(JSON.parse(saved) as [number, number]))
      addEventListener('mousemove', (event) => place(event.clientX, event.clientY), true)
      addEventListener(
        'mousedown',
        () => {
          pointer.style.transform = 'scale(.7)'
          setTimeout(() => (pointer.style.transform = ''), 180)
        },
        true,
      )
      const show = () => {
        const text = sessionStorage.getItem('demo.caption')
        if (!text) {
          bar.style.display = 'none'
          return
        }
        const [act, line] = JSON.parse(text) as [string, string]
        bar.style.display = 'block'
        bar.replaceChildren()
        const strong = document.createElement('strong')
        strong.textContent = act
        bar.append(strong, document.createTextNode(` · ${line}`))
      }
      show()
      addEventListener('demo-caption', show)
    }
    if (document.documentElement) draw()
    else addEventListener('DOMContentLoaded', draw)
    addEventListener('DOMContentLoaded', draw)
  })
}

/** The caption bar: the act and one line of what is happening (presenter pace only). */
export async function say(page: Page, act: string, line: string): Promise<void> {
  if (!presenting) return
  await page.evaluate(
    ([a, l]) => {
      sessionStorage.setItem('demo.caption', JSON.stringify([a, l]))
      dispatchEvent(new Event('demo-caption'))
    },
    [act, line],
  )
  await page.waitForTimeout(1_500) // long enough to start reading before the next click
}

let pointerAt = { x: 720, y: 450 }

/** Moves the mouse to the middle of an element in a visible glide, then waits a moment so the target is seen. */
export async function pointAt(page: Page, target: Locator): Promise<void> {
  if (!presenting) return
  await target.scrollIntoViewIfNeeded()
  const box = await target.boundingBox()
  if (!box) return
  const to = { x: box.x + box.width / 2, y: box.y + box.height / 2 }
  const steps = 70
  for (let step = 1; step <= steps; step++) {
    const t = step / steps
    const ease = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
    await page.mouse.move(pointerAt.x + (to.x - pointerAt.x) * ease, pointerAt.y + (to.y - pointerAt.y) * ease)
    await page.waitForTimeout(16)
  }
  pointerAt = to
  await page.waitForTimeout(1_200)
}

/** A click as the Presenter makes it: glide to the element, pause, click, pause. Plain and fast in CI. */
export async function tap(page: Page, target: Locator): Promise<void> {
  await pointAt(page, target)
  await target.click()
  if (presenting) await page.waitForTimeout(1_500)
}

/** Types into a field: glide to it, then type at a readable speed in presenter pace. */
export async function enter(page: Page, field: Locator, text: string): Promise<void> {
  await pointAt(page, field)
  // A date input takes a whole value at once; a text box is typed at a readable speed.
  if (presenting && (await field.getAttribute('type')) !== 'date') {
    await field.click()
    await field.pressSequentially(text, { delay: 140 })
    await page.waitForTimeout(600)
  } else {
    if (presenting) await field.click()
    await field.fill(text)
  }
}

/** Switches the persona the way a presenter does: the Persona selector in the top bar. */
export async function asPersona(page: Page, key: 'pat' | 'quinn' | 'alex' | 'sam' | 'admin'): Promise<void> {
  const selector = page.getByRole('combobox', { name: 'Persona' })
  await pointAt(page, selector)
  await selector.selectOption(key)
  if (presenting) await page.waitForTimeout(1_500)
}

/** Runs a Demo Controls step by its id, as an admin would, and waits for it to succeed. Returns after the last progress line. */
export async function runStep(page: Page, id: string, timeoutMs = 120_000): Promise<void> {
  const step = page.locator(`[data-step="${id}"]`)
  await tap(page, step.getByRole('button', { name: /^Run / }))
  await page.getByTestId('run-status').and(page.locator('[data-status="succeeded"]')).waitFor({ timeout: timeoutMs })
}

/** The Overview row of a batch (the in-flight row; lot numbers come from the database). */
export function openRow(page: Page, batch: string): Locator {
  return page.locator(`[data-testid=batch-row][data-row-key*="|${batch}|"]`).first()
}
