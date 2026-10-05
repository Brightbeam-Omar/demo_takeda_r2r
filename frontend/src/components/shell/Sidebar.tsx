import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useMe, useReference } from '../../api/queries'
import { PersonaSwitcher } from './PersonaSwitcher'

interface Item {
  to: string
  label: string
  adminOnly?: boolean
}

const ITEMS: Item[] = [
  { to: '/overview', label: 'Overview' },
  { to: '/agents', label: 'Agents' },
  { to: '/sync', label: 'Sync Status' },
  { to: '/audit', label: 'Audit Log' },
  { to: '/admin', label: 'Admin', adminOnly: true },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2 rounded-chip px-3 py-2 ${isActive ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const me = useMe()
  const reference = useReference()
  const isAdmin = me.data?.role === 'admin'

  return (
    <aside
      className={`flex shrink-0 flex-col bg-slate-900 text-slate-100 transition-[width] ${collapsed ? 'w-14' : 'w-60'}`}
      aria-label="Main"
    >
      <div className="flex items-center justify-between px-3 py-4">
        {!collapsed && (
          <div>
            <div className="flex items-center gap-2 text-base font-semibold">
              <span aria-hidden className="grid h-6 w-6 place-items-center rounded-chip bg-indigo-500 text-xs">
                R
              </span>
              R2R Intelligence
            </div>
            <span
              title="DEMO · Phase 1 Trusted Data"
              className="mt-2 inline-block rounded-chip bg-slate-800 px-2 py-0.5 text-xs text-slate-300"
            >
              DEMO · Phase 1
            </span>
          </div>
        )}
        <button
          type="button"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="rounded-chip px-2 py-1 text-slate-400 hover:bg-slate-800"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? '»' : '«'}
        </button>
      </div>
      {!collapsed && (
        <nav className="flex-1 space-y-1 px-2">
          {ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
            <NavLink key={item.to} to={item.to} className={linkClass}>
              {item.label}
            </NavLink>
          ))}
          <span
            aria-disabled="true"
            className="flex items-center gap-2 px-3 py-2 text-slate-500"
            title="Reports arrive in Tier 2"
          >
            Reports
            <span className="rounded-chip bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">Tier 2</span>
          </span>
        </nav>
      )}
      {!collapsed && (
        <div className="space-y-2 border-t border-slate-800 p-3 text-xs text-slate-400">
          <PersonaSwitcher />
          <div>
            <span className="rounded-chip bg-slate-800 px-2 py-0.5">Local demo</span>
          </div>
          <div>{reference.data?.site_name ?? ''}</div>
        </div>
      )}
    </aside>
  )
}
