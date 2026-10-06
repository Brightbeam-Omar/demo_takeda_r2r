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
