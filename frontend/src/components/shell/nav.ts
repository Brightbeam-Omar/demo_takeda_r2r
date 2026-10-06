/** The sidebar menu (05 v2 section 3, F15-FR-02). Routes whose page is not built show a titled placeholder. */
export interface NavItem {
  to: string
  label: string
  icon: string
  /** What the placeholder says for a route that is not built yet. */
  coming?: string
  /** One paragraph on the capability a Tier 2 placeholder stands for (F21-FR-06). */
  about?: string
  /** The roadmap item behind a Tier 2 placeholder, shown beside the Tier 2 tag. */
  roadmap?: string
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
  {
    to: '/admin/upload',
    label: 'Upload Data',
    icon: '⇪',
    coming: 'Tier 2',
    roadmap: 'T2-07',
    about:
      'Bring in data from a spreadsheet when a source system has no interface: choose a file, map its columns to the published fields, preview the rows and load them. The load runs through the same pipeline as every other source, so each number stays explainable. Planned as spreadsheet ingest (T2-07).',
  },
  {
    to: '/admin/mapping',
    label: 'Process / Campaign Mapping',
    icon: '⇄',
    coming: 'Tier 2',
    about:
      'Maintain the link between production processes, campaigns and materials, so the need-by date of a batch follows the right campaign when plans change. Today the campaign comes from the open demand lines of the ERP.',
  },
  {
    to: '/admin/integrations',
    label: 'POC — Integrations',
    icon: '⚯',
    coming: 'Tier 2',
    roadmap: 'T2-01',
    about:
      'See every connected source (ERP, LIMS, QMS and the 3PL feed) with its adapter, its last extraction and its health, and choose the adapter a site uses. Tier 2 adds the 3PL feed and the second ERP adapter.',
  },
  {
    to: '/admin/configuration',
    label: 'Configuration',
    icon: '⚙',
    coming: 'Tier 2',
    about:
      'Edit the site profile from the browser: stages, SLAs, owning teams, reason codes and terminology. Today the profile is a YAML file reviewed with the code, and a change takes effect at the next pipeline run.',
  },
  {
    to: '/admin/sla',
    label: 'SLA Configuration',
    icon: '⏱',
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
