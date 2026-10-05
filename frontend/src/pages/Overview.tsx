import { useCallback, useMemo, useState } from 'react'
import { apiBlob } from '../api/client'
import { useExpectedDeliveries, useMe, useMetrics, useOverview, useReference, useToggleBookmark } from '../api/queries'
import { EmptyState, ErrorState, Skeleton } from '../components/common/States'
import { BatchDrawer } from '../components/drawer/BatchDrawer'
import { NeedByModal } from '../components/edit/NeedByModal'
import { Section } from '../components/common/Section'
import { AdjustedBanner } from '../components/banners/AdjustedBanner'
import { InsightsBanner } from '../components/banners/InsightsBanner'
import { AdjustedNeedByWindow } from '../components/windows/AdjustedNeedByWindow'
import { InsightsWindow } from '../components/windows/InsightsWindow'
import { FilterBar } from '../components/filters/FilterBar'
import { StageStrip, activeTotal } from '../components/pipeline/StageStrip'
import { ExpectedDeliveriesWindow } from '../components/windows/ExpectedDeliveriesWindow'
import { BatchTable } from '../components/table/BatchTable'
import { useToast } from '../components/common/Toasts'
import { canEditNeedBy } from '../lib/roles'
import { saveBlob } from '../lib/download'
import { MetricsRibbon, metricsTitle } from '../components/metrics/MetricsRibbon'
import { useJustSaved } from '../state/just-saved'
import { useRowChanges } from '../state/row-changes'
import { EMPTY_FILTERS, activeFilterCount, toApiParams, useDrawerRow, useUrlFilters } from '../state/url-filters'

export function Overview() {
  const { filters, update, clearAll } = useUrlFilters()
  const drawer = useDrawerRow()
  const [editRow, setEditRow] = useState<string | null>(null)
  const [openWindow, setOpenWindow] = useState<'adjusted' | 'insights' | 'deliveries' | null>(null)
  const justSaved = useJustSaved()
  const reference = useReference()
  const params = toApiParams(filters)
  const overview = useOverview(params)
  const changed = useRowChanges(overview.data, params.toString())
  const metrics = useMetrics(overview.data?.freshness.contract_run_id)
  const stageLabel = useCallback(
    (key: string) => String(reference.data?.stages.find((stage) => stage.stage_key === key)?.label ?? key),
    [reference.data],
  )
  const stageLabels = useMemo(
    () => Object.fromEntries((reference.data?.stages ?? []).map((stage) => [String(stage.stage_key), String(stage.label)])),
    [reference.data],
  )
  const data = overview.data
  const changedKeys = useMemo(() => new Set([...changed, ...justSaved]), [changed, justSaved])
  const me = useMe()
  // Both banners and their windows use every filter except stage (OQ-059(5), OQ-087).
  const bannerParams = useMemo(() => toApiParams({ ...filters, stages: [] }), [filters])
  // Stage 0 follows type, class, campaign and period only: stage, tags, search and bookmarks never apply (OQ-094).
  const deliveryParams = useMemo(
    () => toApiParams({ ...EMPTY_FILTERS, types: filters.types, classes: filters.classes, campaigns: filters.campaigns, period: filters.period, from: filters.from, to: filters.to }),
    [filters],
  )
  const deliveries = useExpectedDeliveries(deliveryParams)
  const airGapCount = data?.alerts.find((alert) => alert.kind === 'air_gap')?.count ?? 0
  const bookmarks = useMemo(() => data?.bookmarks ?? [], [data])
  const bookmarkSet = useMemo(() => new Set(bookmarks), [bookmarks])
  const toggleBookmark = useToggleBookmark()
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
      <main className="flex-1 space-y-5 overflow-auto p-6 pb-20">
        <FilterBar
          reference={reference.data}
          rows={data?.rows ?? []}
          filters={filters}
          stageLabel={stageLabel}
          bookmarks={bookmarks}
          onChange={update}
          onClear={clearAll}
        />
        {overview.isError && !data && (
          <ErrorState what="the overview" error={overview.error} onRetry={() => void overview.refetch()} />
        )}
        {!data && overview.isPending && <Skeleton label="alerts and pipeline" height="h-40" />}
        {data && (
          <section aria-label="Banners" className="space-y-2">
            <AdjustedBanner count={data.adjusted_count} onView={() => setOpenWindow('adjusted')} />
            <InsightsBanner count={airGapCount} onView={() => setOpenWindow('insights')} />
          </section>
        )}
        {data && reference.data && (
          <Section
            title="Pipeline by Stage"
            aside={
              <span className="flex items-center gap-3 text-sm">
                {filters.stages.length > 0 && (
                  <button type="button" className="text-accent hover:underline" onClick={() => update({ stages: [] })}>
                    ✕ Clear {filters.stages.length} {filters.stages.length === 1 ? 'stage' : 'stages'}
                  </button>
                )}
                <span className="text-ink-2" data-testid="active-batches">
                  {activeTotal(data.flow_strip, reference.data.stages)} active batches
                </span>
              </span>
            }
          >
            <StageStrip
              entries={data.flow_strip}
              stages={reference.data.stages}
              mode={data.mode}
              onHoldCount={data.on_hold_count}
              activeStages={filters.stages}
              onHoldActive={filters.flags.includes('on_hold')}
              deliveries={deliveries.data?.count ?? 0}
              onOpenDeliveries={() => setOpenWindow('deliveries')}
              explainParams={toApiParams({ ...filters, stages: [] })}
              onToggleStage={(key) =>
                update({ stages: filters.stages.includes(key) ? filters.stages.filter((stage) => stage !== key) : [...filters.stages, key] })
              }
              onClearStages={() => update({ stages: [] })}
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
        <Section
          title={metrics.data ? metricsTitle(metrics.data.metrics) : 'Weekly Metrics'}
          aside={<code className="font-mono text-xs text-ink-2">Source: weekly_metrics_v</code>}
        >
          {metrics.isError ? (
            <ErrorState what="the weekly metrics" error={metrics.error} onRetry={() => void metrics.refetch()} />
          ) : metrics.data ? (
            metrics.data.metrics.length > 0 ? (
              <MetricsRibbon metrics={metrics.data.metrics} stageLabels={stageLabels} />
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
                bookmarks={bookmarkSet}
                onToggleBookmark={(rowKey, on) =>
                  toggleBookmark.mutate(
                    { rowKey, on },
                    { onError: (error) => notify(`Could not update the bookmark: ${error.message}`, 'error') },
                  )
                }
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
      <AdjustedNeedByWindow open={openWindow === 'adjusted'} onClose={() => setOpenWindow(null)} params={bannerParams} />
      <ExpectedDeliveriesWindow open={openWindow === 'deliveries'} onClose={() => setOpenWindow(null)} params={deliveryParams} />
      <InsightsWindow open={openWindow === 'insights'} onClose={() => setOpenWindow(null)} params={bannerParams} />
      {editRow ? <NeedByModal rowKey={editRow} onClose={() => setEditRow(null)} /> : null}
    </>
  )
}
