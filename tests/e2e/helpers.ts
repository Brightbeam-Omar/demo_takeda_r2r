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
