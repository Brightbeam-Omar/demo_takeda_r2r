import type { RowDetail } from '../api/queries'

/** Small pure helpers shared by the batch windows and the drawer's summary sections (F19). */

type Inbound = RowDetail['inbound_check']

export interface InboundState {
  label: string
  colour: 'green' | 'amber' | 'red' | 'grey'
  /** The overall verdict (CHECK RESULTS). */
  verdict: string
}

/** W2 header: Passed green, Completed (Resolved) amber, Failed or Open red, No status grey. */
export function inboundState(check: Inbound): InboundState {
  switch (check?.status) {
    case 'passed':
      return { label: 'Passed', colour: 'green', verdict: 'Passed' }
    case 'resolved':
      return { label: 'Completed (Resolved)', colour: 'amber', verdict: 'Completed (Resolved)' }
    case 'failed':
      return { label: 'Failed', colour: 'red', verdict: 'Failed' }
    case 'open':
      return { label: 'Open', colour: 'red', verdict: 'Open' }
    default:
      return { label: 'No status', colour: 'grey', verdict: 'No inbound check recorded.' }
  }
}

export const SAMPLE_PILLS = ['all', 'received', 'approved', 'rejected'] as const
export type SamplePill = (typeof SAMPLE_PILLS)[number]

/** Received = registered or in progress (OQ-110); approved and rejected are as in the LIMS. */
export function samplePill(status: string | null): Exclude<SamplePill, 'all'> {
  if (status === 'approved') return 'approved'
  if (status === 'rejected') return 'rejected'
  return 'received'
}

export function sampleCounts(samples: { status: string | null }[]): Record<SamplePill, number> {
  const counts: Record<SamplePill, number> = { all: samples.length, received: 0, approved: 0, rejected: 0 }
  for (const sample of samples) counts[samplePill(sample.status)] += 1
  return counts
}

export type NeedByDelta = { days: number; text: string; tone: 'red' | 'green' } | null

/** `−7d (pulled forward)` in red, `+3d (pushed back)` in green; none for no change or no system date (W6). */
export function needByDelta(system: string | null, adjusted: string | null): NeedByDelta {
  if (!system || !adjusted) return null
  const [sy, sm, sd] = system.split('-').map(Number) as [number, number, number]
  const [ay, am, ad] = adjusted.split('-').map(Number) as [number, number, number]
  const days = Math.round((Date.UTC(ay, am - 1, ad) - Date.UTC(sy, sm - 1, sd)) / 86_400_000)
  if (days === 0) return null
  return days < 0
    ? { days, text: `−${-days}d (pulled forward)`, tone: 'red' }
    : { days, text: `+${days}d (pushed back)`, tone: 'green' }
}

export const OTHER_REASON = 'OTHER'
