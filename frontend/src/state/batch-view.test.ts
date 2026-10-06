import { expect, test } from 'vitest'
import { readBatchView, withDrawer, withWindow, withoutWindow } from './batch-view'

const params = (query: string) => new URLSearchParams(query)

test('F19-FR-01: ?row= alone is the drawer and no window', () => {
  expect(readBatchView(params('row=RM1%7CB1%7C1'))).toEqual({ drawerRow: 'RM1|B1|1', win: null, winRow: null })
  expect(readBatchView(params('q=B1'))).toEqual({ drawerRow: null, win: null, winRow: null })
})

test('F19-FR-01: ?win=&row= is a window alone: the drawer is not open behind it', () => {
  expect(readBatchView(params('win=quality&row=R1'))).toEqual({ drawerRow: null, win: 'quality', winRow: 'R1' })
})

test('F19-FR-01: a window over the drawer leaves the drawer showing', () => {
  expect(readBatchView(params('win=needby&row=R1&drawer=open'))).toEqual({ drawerRow: 'R1', win: 'needby', winRow: 'R1' })
})

test('F19-FR-01: an unknown window name or a window without a row is ignored', () => {
  expect(readBatchView(params('win=history&row=R1'))).toEqual({ drawerRow: 'R1', win: null, winRow: null })
  expect(readBatchView(params('win=quality'))).toEqual({ drawerRow: null, win: null, winRow: null })
})

test('F19-FR-01: opening a window from the table gives win and row; from the drawer it also marks the drawer', () => {
  expect(withWindow(params('q=B1'), 'inbound', 'R1').toString()).toBe('q=B1&win=inbound&row=R1')
  expect(withWindow(params('q=B1&row=R1'), 'status', 'R1').toString()).toBe('q=B1&row=R1&win=status&drawer=open')
})

test('F19-FR-01: closing a window leaves the drawer open only when it was open underneath', () => {
  expect(withoutWindow(params('q=B1&win=inbound&row=R1')).toString()).toBe('q=B1')
  expect(withoutWindow(params('q=B1&row=R1&win=status&drawer=open')).toString()).toBe('q=B1&row=R1')
})

test('F19-FR-01: opening or closing the drawer drops any window and keeps the other filters', () => {
  expect(withDrawer(params('q=B1&win=inbound&row=R1'), 'R2').toString()).toBe('q=B1&row=R2')
  expect(withDrawer(params('q=B1&row=R2'), null).toString()).toBe('q=B1')
})
