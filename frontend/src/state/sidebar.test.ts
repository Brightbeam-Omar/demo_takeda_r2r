import { beforeEach, expect, test } from 'vitest'
import { isCollapsed, resetSidebar, setDrawerOpen, toggleSidebar } from './sidebar'

beforeEach(resetSidebar)

test('F19 review: opening the drawer collapses the sidebar and closing it restores it', () => {
  expect(isCollapsed()).toBe(false)
  setDrawerOpen(true)
  expect(isCollapsed()).toBe(true)
  setDrawerOpen(false)
  expect(isCollapsed()).toBe(false)
})

test('F19 review: a sidebar the user collapsed stays collapsed after the drawer closes', () => {
  toggleSidebar()
  setDrawerOpen(true)
  expect(isCollapsed()).toBe(true)
  setDrawerOpen(false)
  expect(isCollapsed()).toBe(true)
})

test('F19 review: expanding by hand while the drawer is open lasts until it closes, then the user state returns', () => {
  setDrawerOpen(true)
  toggleSidebar()
  expect(isCollapsed()).toBe(false)
  setDrawerOpen(false)
  setDrawerOpen(true)
  expect(isCollapsed()).toBe(true) // a new drawer collapses it again
})
