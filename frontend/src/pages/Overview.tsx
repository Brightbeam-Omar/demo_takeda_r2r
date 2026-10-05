import { useCallback } from 'react'
import { useClock, useMetrics, useOverview, useReference } from '../api/queries'
import { Section } from '../components/common/Section'
import { FiltersBand } from '../components/filters/FiltersBand'
import { PeriodSelector } from '../components/filters/PeriodSelector'
import { AlertsBand } from '../components/flow-strip/AlertsBand'
import { FlowStrip } from '../components/flow-strip/FlowStrip'
import { MetricsRibbon } from '../components/metrics/MetricsRibbon'
import { TopBar } from '../components/shell/TopBar'
import { toApiParams, useUrlFilters } from '../state/url-filters'

export function Overview() {
  const { filters, update, clearAll } = useUrlFilters()
  const reference = useReference()
  const clock = useClock()
  const overview = useOverview(toApiParams(filters))
  const metrics = useMetrics(overview.data?.freshness.contract_run_id)
  const stageLabel = useCallback(
    (key: string) => String(reference.data?.stages.find((stage) => stage.stage_key === key)?.label ?? key),
    [reference.data],
  )
  const data = overview.data

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
        {metrics.data && (
          <Section title="Weekly Metrics">
            <MetricsRibbon metrics={metrics.data.metrics} />
          </Section>
        )}
        <p className="text-sm text-slate-500">{data ? `${data.total} batches` : ''}</p>
      </main>
    </>
  )
}
