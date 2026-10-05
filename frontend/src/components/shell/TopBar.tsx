import type { ReactNode } from 'react'
import { useMe } from '../../api/queries'
import { roleLabel } from './PersonaSwitcher'

export function TopBar({ title, children }: { title: string; children?: ReactNode }) {
  const me = useMe()
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-6">
      <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
      <div className="ml-auto flex items-center gap-4">
        {children}
        <span
          data-testid="user-chip"
          className="rounded-chip bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700"
        >
          {me.data ? `${me.data.display_name} · ${roleLabel(me.data.role)}` : '…'}
        </span>
      </div>
    </header>
  )
}
