import { ApiError, apiHeaders } from './client'

/** One scenario step as the Demo Controls page lists it (F13-FR-03). */
export interface DemoStep {
  id: string
  title: string
  talk_track: string
  preconditions: 'met' | 'unmet' | 'unknown'
  messages: string[]
  actions: string[]
}

export interface RunEvent {
  seq: number
  kind: 'start' | 'action_start' | 'action_done' | 'line' | 'done' | 'failed'
  message: string
  elapsed_ms: number
  status?: string
}

async function request<T>(method: 'GET' | 'POST', path: string): Promise<T> {
  const response = await fetch(`/api/demo${path}`, { method, headers: apiHeaders() })
  if (!response.ok) {
    let message = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      const detail = body.detail as { message?: string } | string | undefined
      message = typeof detail === 'string' ? detail : (detail?.message ?? message)
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, message || `HTTP ${response.status}`)
  }
  return (await response.json()) as T
}

export const fetchSteps = () => request<DemoStep[]>('GET', '/steps')
export const startStep = (id: string) => request<{ run_id: string }>('POST', `/steps/${encodeURIComponent(id)}/run`)
export const startReset = () => request<{ run_id: string }>('POST', '/reset')

/** Splits a Server-Sent Events text into its `data:` payloads; returns what is left of an unfinished frame. */
export function parseFrames(buffer: string): { events: RunEvent[]; rest: string } {
  const frames = buffer.split('\n\n')
  const rest = frames.pop() ?? ''
  const events: RunEvent[] = []
  for (const frame of frames) {
    const data = frame.split('\n').find((line) => line.startsWith('data: '))
    if (data) events.push(JSON.parse(data.slice('data: '.length)) as RunEvent)
  }
  return { events, rest }
}

/**
 * Follows a run until it ends (F13-FR-06). A plain `fetch` stream rather than `EventSource`: the page has to send
 * the `X-Demo-User` header, which `EventSource` cannot. If the connection drops, it resumes after the last line seen
 * (the server replays from `?after=`), so no line is lost or shown twice.
 */
export async function followRun(runId: string, onEvent: (event: RunEvent) => void, signal: AbortSignal): Promise<void> {
  let next = 0
  let ended = false
  for (let attempt = 0; attempt < 4 && !ended && !signal.aborted; attempt += 1) {
    try {
      const response = await fetch(`/api/demo/runs/${encodeURIComponent(runId)}/events?after=${next}`, { headers: apiHeaders(), signal })
      if (!response.ok || !response.body) throw new ApiError(response.status, `HTTP ${response.status}`)
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parsed = parseFrames(buffer)
        buffer = parsed.rest
        for (const event of parsed.events) {
          next = event.seq + 1
          onEvent(event)
          if (event.kind === 'done' || event.kind === 'failed') ended = true
        }
      }
    } catch (error) {
      if (signal.aborted) return
      if (attempt === 3) throw error
    }
  }
}
