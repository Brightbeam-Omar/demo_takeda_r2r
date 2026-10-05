import { expect, test } from 'vitest'
import type { Row } from '../api/queries'
import { changedRowKeys, signatures } from './row-changes'

const row = (key: string, stage: string, due: string) =>
  ({ row_key: key, stage_key: stage, plan: { expected_completion: due } }) as unknown as Row

test('F10-FR-11: a row that changed stage, changed due date or is new counts as moved', () => {
  const before = signatures([row('a', 'qc_testing', '2026-10-15'), row('b', 'sampling', '2026-10-16'), row('c', 'receipt', '2026-10-17')])
  const after = signatures([row('a', 'qa_release', '2026-10-20'), row('b', 'sampling', '2026-10-16'), row('c', 'receipt', '2026-10-18'), row('d', 'receipt', '2026-10-19')])
  expect([...changedRowKeys(before, after)].sort()).toEqual(['a', 'c', 'd'])
})
