import { useClock, useMe } from '../../api/queries'
import { useUrlFilters } from '../../state/url-filters'
import { DemoClock } from './DemoClock'
import { FreshnessPill } from './FreshnessPill'
import { PeriodPicker } from './PeriodPicker'
import { roleLabel } from './PersonaSwitcher'

export function TopBar({ title }: { title: string }) {
  const me = useMe()
  const clock = useClock()
  const { filters, update } = useUrlFilters()
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-hairline bg-white px-6">
      <h1 className="text-lg font-semibold text-ink">{title}</h1>
      <FreshnessPill />
      <div className="ml-auto flex items-center gap-4">
        <span className="flex items-center gap-2 text-sm text-ink-2">
          Period:
          <PeriodPicker filters={filters} today={clock.data?.today_local ?? '2026-10-12'} onChange={update} />
        </span>
        <DemoClock />
        <span data-testid="user-chip" className="rounded-pill bg-panel px-3 py-1.5 text-sm font-medium text-ink">
          {me.data ? `${me.data.display_name} · ${roleLabel(me.data.role)}` : '…'}
        </span>
      </div>
    </header>
  )
}
