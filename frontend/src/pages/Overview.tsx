import { useCallback, useMemo, useState } from 'react'
import { apiBlob } from '../api/client'
import { useClock, useMe, useMetrics, useOverview, useReference } from '../api/queries'
import { EmptyState, ErrorState, Skeleton } from '../components/common/States'
import { BatchDrawer } from '../components/drawer/BatchDrawer'
import { NeedByModal } from '../components/edit/NeedByModal'
import { Section } from '../components/common/Section'
import { FiltersBand } from '../components/filters/FiltersBand'
import { PeriodSelector } from '../components/filters/PeriodSelector'
import { AlertsBand } from '../components/flow-strip/AlertsBand'
import { FlowStrip } from '../components/flow-strip/FlowStrip'
import { BatchTable } from '../components/table/BatchTable'
import { useToast } from '../components/common/Toasts'
import { canEditNeedBy } from '../lib/roles'
import { saveBlob } from '../lib/download'
import { MetricsRibbon } from '../components/metrics/MetricsRibbon'
import { TopBar } from '../components/shell/TopBar'
import { useJustSaved } from '../state/just-saved'
import { useRowChanges } from '../state/row-changes'
import { activeFilterCount, toApiParams, useDrawerRow, useUrlFilters } from '../state/url-filters'

export function Overview() {
  const { filters, update, clearAll } = useUrlFilters()
  const drawer = useDrawerRow()
  const [editRow, setEditRow] = useState<string | null>(null)
  const justSaved = useJustSaved()
  const reference = useReference()
  const clock = useClock()
  const params = toApiParams(filters)
  const overview = useOverview(params)
  const changed = useRowChanges(overview.data, params.toString())
  const metrics = useMetrics(overview.data?.freshness.contract_run_id)
  const stageLabel = useCallback(
    (key: string) => String(reference.data?.stages.find((stage) => stage.stage_key === key)?.label ?? key),
    [reference.data],
  )
  const data = overview.data
  const changedKeys = useMemo(() => new Set([...changed, ...justSaved]), [changed, justSaved])
  const me = useMe()
  const { notify } = useToast()
  const [exporting, setExporting] = useState(false)
  // Only planners and admins may adjust a need-by (F09); everyone else sees the pencil disabled (OQ-063).
  const canEdit = canEditNeedBy(me.data?.role)
  const stageIndex = useMemo(
    () => new Map((reference.data?.stages ?? []).map((stage, index) => [String(stage.stage_key), index])),
    [reference.data],
  )
  const exportCsv = async () => {
    setExporting(true)
    try {
      saveBlob(await apiBlob('/export.csv', toApiParams(filters)), 'r2r-overview.csv')
    } catch (error) {
      notify(`Export failed: ${(error as Error).message}`, 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <TopBar title="Overview">
        <PeriodSelector filters={filters} today={clock.data?.today_local ?? '2026-10-12'} onChange={update} />
      </TopBar>
      <main className="flex-1 space-y-5 overflow-auto p-6">
        <FiltersBand
          reference={reference.data}
          rows={data?.rows ?? []}
          filters={filters}
          stageLabel={stageLabel}
          onChange={update}
          onClear={clearAll}
        />
        {overview.isError && !data && (
          <ErrorState what="the overview" error={overview.error} onRetry={() => void overview.refetch()} />
        )}
        {!data && overview.isPending && <Skeleton label="alerts and pipeline" height="h-40" />}
        {data && <AlertsBand alerts={data.alerts} onFilter={update} />}
        {data && reference.data && (
          <Section title="Pipeline by Stage">
            <FlowStrip
              entries={data.flow_strip}
              stages={reference.data.stages}
              mode={data.mode}
              onHoldCount={data.on_hold_count}
              activeStage={filters.stage}
              onHoldActive={filters.flags.includes('on_hold')}
              explainParams={toApiParams({ ...filters, stage: null })}
              onToggleStage={(key) => update({ stage: filters.stage === key ? null : key })}
              onToggleHold={() =>
                update({
                  flags: filters.flags.includes('on_hold')
                    ? filters.flags.filter((flag) => flag !== 'on_hold')
                    : [...filters.flags, 'on_hold'],
                })
              }
            />
          </Section>
        )}
        <Section title="Weekly Metrics">
          {metrics.isError ? (
            <ErrorState what="the weekly metrics" error={metrics.error} onRetry={() => void metrics.refetch()} />
          ) : metrics.data ? (
            metrics.data.metrics.length > 0 ? (
              <MetricsRibbon metrics={metrics.data.metrics} />
            ) : (
              <EmptyState>No metrics are published yet.</EmptyState>
            )
          ) : (
            <Skeleton label="weekly metrics" />
          )}
        </Section>
        <Section title="Batches">
          {data ? (
            data.total === 0 && overview.isSuccess && activeFilterCount(filters) === 0 && filters.period === 'all' ? (
              <EmptyState>No batches yet. The pipeline has not published any data.</EmptyState>
            ) : (
              <BatchTable
                rows={data.rows}
                stageIndex={stageIndex}
                canEdit={canEdit}
                changedKeys={changedKeys}
                onEditRow={setEditRow}
                onOpenRow={drawer.open}
                toolbar={
                  <button
                    type="button"
                    disabled={exporting}
                    className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400 disabled:opacity-50"
                    onClick={() => void exportCsv()}
                  >
                    Export CSV
                  </button>
                }
              />
            )
          ) : (
            !overview.isError && <Skeleton label="batches" height="h-96" />
          )}
        </Section>
      </main>
      <BatchDrawer rowKey={drawer.row} onOpenRow={drawer.open} canEdit={canEdit} onEdit={setEditRow} />
      {editRow ? <NeedByModal rowKey={editRow} onClose={() => setEditRow(null)} /> : null}
    </>
  )
}
