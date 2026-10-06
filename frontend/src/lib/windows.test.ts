import { expect, test } from 'vitest'
import { inboundState, needByDelta, sampleCounts } from './windows'

test('F19-FR-01: the inbound header reads Passed green, Completed (Resolved) amber, Failed or Open red, No status grey', () => {
  const state = (status: string) => inboundState({ status } as never)
  expect([state('passed'), state('resolved'), state('failed'), state('open')].map((s) => [s.label, s.colour])).toEqual([
    ['Passed', 'green'],
    ['Completed (Resolved)', 'amber'],
    ['Failed', 'red'],
    ['Open', 'red'],
  ])
  expect(inboundState(null)).toEqual({ label: 'No status', colour: 'grey', verdict: 'No inbound check recorded.' })
})

test('F19-AC-05: the sample pills count Received (registered and in progress), Approved and Rejected', () => {
  const statuses = ['registered', 'in_progress', 'approved', 'rejected', 'approved'].map((status) => ({ status }))
  expect(sampleCounts(statuses)).toEqual({ all: 5, received: 2, approved: 2, rejected: 1 })
  expect(sampleCounts([{ status: 'in_progress' }])).toEqual({ all: 1, received: 1, approved: 0, rejected: 0 })
  expect(sampleCounts([])).toEqual({ all: 0, received: 0, approved: 0, rejected: 0 })
})

test('F19-AC-06: pulling the date forward reads −7d (pulled forward) in red, pushing it back +3d in green', () => {
  expect(needByDelta('2026-12-03', '2026-11-26')).toEqual({ days: -7, text: '−7d (pulled forward)', tone: 'red' })
  expect(needByDelta('2026-12-03', '2026-12-06')).toEqual({ days: 3, text: '+3d (pushed back)', tone: 'green' })
  expect(needByDelta('2026-12-03', '2026-12-03')).toBeNull()
  expect(needByDelta(null, '2026-12-03')).toBeNull()
})
