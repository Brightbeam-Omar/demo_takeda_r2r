import { NavLink } from 'react-router-dom'
import { useMe, useReference, useUsers } from '../../api/queries'
import { toggleSidebar, useSidebarCollapsed } from '../../state/sidebar'
import { PersonaSwitcher } from './PersonaSwitcher'
import { ADMIN, VIEWS, type NavItem } from './nav'

const linkClass =
  (collapsed: boolean) =>
  ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 rounded-chip px-3 py-1.5 ${collapsed ? 'justify-center px-0' : ''} ${isActive ? 'bg-accent-tint font-semibold text-accent' : 'text-ink hover:bg-panel'}`

function Group({ title, items, collapsed }: { title: string; items: NavItem[]; collapsed: boolean }) {
  return (
    <div className="mb-4">
      {!collapsed && (
        <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-2">{title}</div>
      )}
      <ul className="space-y-0.5">
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end
              title={collapsed ? item.label : undefined}
              aria-label={item.label}
              data-testid={`nav-${item.to.slice(1).replace(/\//g, '-')}`}
              className={linkClass(collapsed)}
            >
              <span aria-hidden className="w-4 text-center text-ink-2">
                {item.icon}
              </span>
              {!collapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Sidebar() {
  const collapsed = useSidebarCollapsed()
  const me = useMe()
  const users = useUsers()
  const reference = useReference()
  const demoMode = users.data !== undefined // /api/users answers only in DEMO_MODE (F10-FR-02)
  const hidePlaceholders = reference.data?.demo?.hide_placeholders === true // F14-FR-16: only ever true in DEMO_MODE
  const admin = ADMIN.filter(
    (item) => (!item.demoAdminOnly || (demoMode && me.data?.role === 'admin')) && !(hidePlaceholders && item.coming),
  )

  return (
    <aside
      data-testid="sidebar"
      aria-label="Main"
      className={`flex shrink-0 flex-col border-r border-hairline bg-white transition-[width] ${collapsed ? 'w-14' : 'w-[232px]'}`}
    >
      <div className="flex items-start justify-between px-3 py-4">
        {!collapsed && (
          <div>
            <div className="flex items-center gap-2 text-base font-bold text-ink">
              <span aria-hidden className="grid h-6 w-6 place-items-center rounded-chip bg-accent text-xs text-white">
                R
              </span>
              R2R Intelligence
            </div>
            <div className="mt-1 text-xs text-ink-2">Phase 1: Trusted Data</div>
            <span
              data-testid="release-badge"
              className="mt-2 inline-block rounded-pill bg-accent-tint px-2 py-0.5 text-[11px] font-semibold text-accent"
            >
              {reference.data?.release_badge ?? 'ALPHA – LOCAL'}
            </span>
          </div>
        )}
        <button
          type="button"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="rounded-chip px-2 py-1 text-ink-2 hover:bg-panel"
          onClick={toggleSidebar}
        >
          {collapsed ? '»' : '«'}
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2" aria-label="Pages">
        <Group title="VIEWS" items={VIEWS} collapsed={collapsed} />
        <Group title="ADMIN" items={admin} collapsed={collapsed} />
      </nav>
      {demoMode && (
        <div className={`space-y-2 border-t border-hairline text-xs text-ink-2 ${collapsed ? 'p-1.5' : 'p-3'}`}>
          <PersonaSwitcher compact={collapsed} />
          {!collapsed && <div>{reference.data?.site_name ?? ''}</div>}
        </div>
      )}
    </aside>
  )
}
