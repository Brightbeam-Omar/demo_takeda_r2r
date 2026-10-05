import { useCallback } from 'react'
import { useOverview, useReference } from '../api/queries'
import { FiltersBand } from '../components/filters/FiltersBand'
import { TopBar } from '../components/shell/TopBar'
import { toApiParams, useUrlFilters } from '../state/url-filters'

export function Overview() {
  const { filters, update, clearAll } = useUrlFilters()
  const reference = useReference()
  const overview = useOverview(toApiParams(filters))
  const stageLabel = useCallback(
    (key: string) => String(reference.data?.stages.find((stage) => stage.stage_key === key)?.label ?? key),
    [reference.data],
  )

  return (
    <>
      <TopBar title="Overview" />
      <main className="flex-1 space-y-4 overflow-auto p-6">
        <FiltersBand
          reference={reference.data}
          rows={overview.data?.rows ?? []}
          filters={filters}
          stageLabel={stageLabel}
          onChange={update}
          onClear={clearAll}
        />
        <p className="text-sm text-slate-500">{overview.data ? `${overview.data.total} batches` : ''}</p>
      </main>
    </>
  )
}
