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
