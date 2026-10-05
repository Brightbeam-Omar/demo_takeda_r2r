import type { components } from './schema'
import { getPersona } from '../state/persona'

export type Schemas = components['schemas']

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Every request carries the chosen persona (F10-FR-02). With none chosen the server default applies. */
export function apiHeaders(): Record<string, string> {
  const persona = getPersona()
  return persona ? { 'X-Demo-User': persona } : {}
}

async function failure(response: Response): Promise<ApiError> {
  let detail = response.statusText
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') detail = body.detail
  } catch {
    // keep the status text
  }
  return new ApiError(response.status, detail || `HTTP ${response.status}`)
}

export async function apiGet<T>(path: string, params?: URLSearchParams): Promise<T> {
  const query = params && [...params].length > 0 ? `?${params.toString()}` : ''
  const response = await fetch(`/api${path}${query}`, { headers: apiHeaders() })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

export async function apiBlob(path: string, params?: URLSearchParams): Promise<Blob> {
  const query = params && [...params].length > 0 ? `?${params.toString()}` : ''
  const response = await fetch(`/api${path}${query}`, { headers: apiHeaders() })
  if (!response.ok) throw await failure(response)
  return response.blob()
}

export async function apiSend<T>(method: 'POST' | 'PUT', path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...apiHeaders() },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}
