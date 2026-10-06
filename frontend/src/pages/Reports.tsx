import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiBlob } from '../api/client'
import { useReport } from '../api/queries'
import { useToast } from '../components/common/Toasts'
import { saveBlob } from '../lib/download'
import { formatDate } from '../lib/format'
import { isTab, TABS, type Summary, type TabKey } from '../lib/reports'
import { Adherence } from './reports/Adherence'
import { ExecutiveSummary } from './reports/ExecutiveSummary'
import { LateItems } from './reports/LateItems'
import { ReleaseRate } from './reports/ReleaseRate'
import { SlaPerformance } from './reports/SlaPerformance'
import { Trends } from './reports/Trends'

const TAB_VIEWS: Record<TabKey, (props: { params: URLSearchParams }) => React.JSX.Element> = {
  summary: ExecutiveSummary,
  sla: SlaPerformance,
  trends: Trends,
  late: LateItems,
  'release-rate': ReleaseRate,
  adherence: Adherence,
}

/** Reports & Metrics: six tabs and a year selector (F20). The tab and the year live in the URL. */
export function Reports() {
  const [search, setSearch] = useSearchParams()
  const requested = search.get('tab')
  const tab: TabKey = isTab(requested) ? requested : 'summary'
  const year = search.get('year')
  const params = new URLSearchParams()
  if (year) params.set('year', year)
  const meta = useReport<Summary>('summary', params)
  const { notify } = useToast()
  const [busy, setBusy] = useState(false)
  const active = TABS.find((entry) => entry.key === tab)!
  const View = TAB_VIEWS[tab]

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(search)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null) next.delete(key)
      else next.set(key, value)
    }
    setSearch(next, { replace: true })
  }
  const download = async () => {
    setBusy(true)
    try {
      saveBlob(await apiBlob(`/reports/${tab}/export.csv`, params), `${tab}.csv`)
    } catch (error) {
      notify(`Export failed: ${(error as Error).message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  const years = meta.data?.years ?? []
  const awaiting = meta.data?.awaiting_signal ?? []
  const coverage = meta.data?.coverage_from
  return (
    <main className="flex-1 overflow-auto px-6 pt-4 pb-20" data-testid="reports-page">
      <div className="flex items-end justify-between border-b border-hairline">
        <div role="tablist" aria-label="Reports" className="flex gap-1">
          {TABS.map((entry) => (
            <button
              key={entry.key}
              role="tab"
              type="button"
              aria-selected={tab === entry.key}
              data-testid={`reports-tab-${entry.key}`}
              className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === entry.key ? 'border-accent font-semibold text-accent' : 'border-transparent text-ink-2 hover:text-ink'}`}
              onClick={() => update({ tab: entry.key })}
            >
              {entry.label}
            </button>
          ))}
        </div>
        <label className="mb-2 flex items-center gap-2 text-sm text-ink-2">
          Year
          <select
            data-testid="reports-year"
            value={meta.data?.year ?? ''}
            disabled={!active.usesYear || years.length === 0}
            title={active.usesYear ? undefined : 'This tab is as of the demo date'}
            className="rounded-chip border border-hairline bg-white px-2 py-1 text-sm text-ink disabled:opacity-50"
            onChange={(event) => update({ year: event.target.value })}
          >
            {years.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      {awaiting.length > 0 && (
        <div role="note" data-testid="reports-na-banner" className="mt-3 rounded-card border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-900">
          {awaiting.map((metric) => metric.metric_id).join(', ')} show N/A until their feeds are connected.
        </div>
      )}
      <div className="mt-3 mb-3 flex items-center justify-between">
        <span className="text-xs text-ink-2" data-testid="reports-coverage">
          {coverage ? `Coverage from ${formatDate(coverage)}` : ''}
        </span>
        <button
          type="button"
          disabled={busy}
          data-testid="reports-export"
          className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400 disabled:opacity-50"
          onClick={() => void download()}
        >
          ↓ Export
        </button>
      </div>
      <View params={params} />
    </main>
  )
}
