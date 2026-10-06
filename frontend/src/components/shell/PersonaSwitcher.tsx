import { useUsers, useMe } from '../../api/queries'
import { setPersona } from '../../state/persona'

/** DEMO_MODE only: when `/api/users` is not available (404) the switcher does not render (F10-FR-02). */
/** `compact` (collapsed sidebar): a narrow select that shows only the first name, so the persona stays reachable. */
export function PersonaSwitcher({ compact = false }: { compact?: boolean }) {
  const users = useUsers()
  const me = useMe()
  if (!users.data) return null
  return (
    <label className="block">
      <span className={compact ? 'sr-only' : 'mb-1 block'}>Persona</span>
      <select
        className={`w-full rounded-chip border border-hairline bg-white py-1.5 text-ink ${compact ? 'px-0 text-xs' : 'px-2 text-sm'}`}
        value={me.data?.user_key ?? ''}
        onChange={(event) => setPersona(event.target.value)}
      >
        {users.data.map((user) => (
          <option key={user.user_key} value={user.user_key}>
            {compact ? user.display_name : `${user.display_name} · ${roleLabel(user.role)}`}
          </option>
        ))}
      </select>
    </label>
  )
}

const ROLE_LABELS: Record<string, string> = {
  planner: 'Planner',
  qc_lead: 'QC Lead',
  qa_release: 'QA Release',
  viewer: 'Viewer',
  admin: 'Admin',
}

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role
}
