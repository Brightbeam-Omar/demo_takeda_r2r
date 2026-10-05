import { useUsers, useMe } from '../../api/queries'
import { setPersona } from '../../state/persona'

/** DEMO_MODE only: when `/api/users` is not available (404) the switcher does not render (F10-FR-02). */
export function PersonaSwitcher() {
  const users = useUsers()
  const me = useMe()
  if (!users.data) return null
  return (
    <label className="block">
      <span className="mb-1 block">Persona</span>
      <select
        className="w-full rounded-chip border border-hairline bg-white px-2 py-1.5 text-sm text-ink"
        value={me.data?.user_key ?? ''}
        onChange={(event) => setPersona(event.target.value)}
      >
        {users.data.map((user) => (
          <option key={user.user_key} value={user.user_key}>
            {user.display_name} · {roleLabel(user.role)}
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
