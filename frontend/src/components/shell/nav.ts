/** The sidebar menu (05 v2 section 3, F15-FR-02). Routes whose page is not built show a titled placeholder. */
export interface NavItem {
  to: string
  label: string
  icon: string
  /** What the placeholder says for a route that is not built yet. */
  coming?: string
  /** Only in DEMO_MODE, and only for the admin role. */
  demoAdminOnly?: boolean
}

export const VIEWS: NavItem[] = [
  { to: '/overview', label: 'Overview', icon: '▦' },
  {
    to: '/reports',
    label: 'Reports & Metrics',
    icon: '▤',
  },
  { to: '/agents', label: 'Agents', icon: '✦', coming: 'Coming in F12' },
]

export const ADMIN: NavItem[] = [
  {
    to: '/admin/team',
    label: 'Team Dashboard',
    icon: '◉',
  },
  { to: '/admin/audit', label: 'Audit Log', icon: '☰' },
  {
    to: '/admin/schema',
    label: 'Schema Reference',
    icon: '▥',
  },
  { to: '/admin/upload', label: 'Upload Data', icon: '⇪', coming: 'Tier 2' },
  {
    to: '/admin/mapping',
    label: 'Process / Campaign Mapping',
    icon: '⇄',
    coming: 'Tier 2',
  },
  {
    to: '/admin/integrations',
    label: 'POC — Integrations',
    icon: '⚯',
    coming: 'Tier 2',
  },
  {
    to: '/admin/configuration',
    label: 'Configuration',
    icon: '⚙',
    coming: 'Tier 2',
  },
  {
    to: '/admin/sla',
    label: 'SLA Configuration',
    icon: '⏱',
    coming: 'Coming in F21',
  },
  { to: '/admin/sync', label: 'Sync Status', icon: '⟳' },
  { to: '/admin/webhooks', label: 'Webhook Sync Status', icon: '⇋' },
  {
    to: '/admin/demo',
    label: 'Demo Controls',
    icon: '▶',
    coming: 'Coming in F13',
    demoAdminOnly: true,
  },
  { to: '/admin/feedback', label: 'Feedback', icon: '✎' },
]

const TITLES: Record<string, string> = {
  '/overview': 'R2R Overview',
  '/reports': 'Reports & Metrics',
  '/agents': 'Agents',
  '/admin/audit': 'Audit Log',
  '/admin/sync': 'Sync Status',
  '/admin/webhooks': 'Webhook Sync Status',
  '/admin/feedback': 'Feedback',
  '/admin/demo': 'Demo Controls',
}

export function pageTitle(pathname: string): string {
  const exact = TITLES[pathname]
  if (exact) return exact
  return [...VIEWS, ...ADMIN].find((item) => item.to === pathname)?.label ?? 'R2R Overview'
}
