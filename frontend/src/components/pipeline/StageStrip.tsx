import { Fragment } from 'react'
import type { Overview, Reference } from '../../api/queries'
import { ExpectedDeliveryCard } from './ExpectedDeliveryCard'
import { OnHoldCard } from './OnHoldCard'
import { StageCard } from './StageCard'

type Entry = Overview['flow_strip'][number]

interface Props {
  entries: Entry[]
  stages: Reference['stages']
  mode: Overview['mode']
  onHoldCount: number
  activeStages: string[]
  onHoldActive: boolean
  /** Open PO lines (Stage 0), from the expected-deliveries endpoint. */
  deliveries: number
  onOpenDeliveries: () => void
  onToggleStage: (stageKey: string) => void
  onClearStages: () => void
  onToggleHold: () => void
  /** The filters behind the counts, without the stage filter, so a flow explanation matches the card. */
  explainParams?: URLSearchParams
}

export const MODE_CAPTION: Record<Overview['mode'], string> = {
  snapshot: 'Snapshot — all active batches',
  due_in_period: 'Due in period — active batches',
}

const DELIVERY_CAPTION: Record<Overview['mode'], string> = {
  snapshot: 'Open PO lines',
  due_in_period: 'Due this period',
}

function withField(base: URLSearchParams | undefined, field: string): URLSearchParams {
  const params = new URLSearchParams(base)
  params.set('field', field)
  return params
}

/** "N skip call-off": the first two words of the label, lower case except acronyms, hyphenated. */
export function skipNoun(label: string): string {
  return label
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => (word === word.toUpperCase() ? word : word.toLowerCase()))
    .join('-')
}

/** Open (not released) lots across the entries: the "Active batches" total. */
export function activeTotal(entries: Entry[], stages: Reference['stages']): number {
  const terminal = new Set(stages.filter((stage) => stage.terminal).map((stage) => String(stage.stage_key)))
  return entries.filter((entry) => !terminal.has(entry.stage_key)).reduce((sum, entry) => sum + entry.count, 0)
}

/** F17-FR-04/05: Expected Delivery, Total Pipeline, one card per visible stage with arrows between, then On Hold. */
export function StageStrip({
  entries, stages, mode, onHoldCount, activeStages, onHoldActive, deliveries, onOpenDeliveries,
  onToggleStage, onClearStages, onToggleHold, explainParams,
}: Props) {
  const byKey = new Map(entries.map((entry) => [entry.stage_key, entry]))
  const visible = stages.filter((stage) => stage.show_card !== false)
  const sla = new Map(stages.map((stage) => [String(stage.stage_key), Number(stage.sla_days ?? 0)]))
  const total = activeTotal(entries, stages)
  return (
    <div className="space-y-1">
      <p className="text-xs text-ink-2" data-testid="flow-caption">
        ▦ {MODE_CAPTION[mode]}
      </p>
      <div className="flex items-stretch gap-1.5 overflow-x-auto pb-1">
        <ExpectedDeliveryCard count={deliveries} caption={DELIVERY_CAPTION[mode]} onOpen={onOpenDeliveries} />
        <StageCard
          testId="flow-total"
          eyebrow="All stages"
          title="Total Pipeline"
          count={total}
          selected={activeStages.length === 0}
          onClick={onClearStages}
          detail="Active batches"
        />
        {visible.map((stage, index) => {
          const key = String(stage.stage_key)
          const entry = byKey.get(key)
          if (!entry) return null
          const days = sla.get(key) ?? 0
          return (
            <Fragment key={key}>
              <span aria-hidden className="flex items-center text-ink-3">
                ▸
              </span>
              <StageCard
                testId={`flow-${key}`}
                eyebrow={`Stage ${index + 1}`}
                title={entry.label}
                count={entry.count}
                selected={activeStages.includes(key)}
                onClick={() => onToggleStage(key)}
                detail={days > 0 ? `SLA ${days} d` : undefined}
                late={entry.late_count}
                skip={entry.skip_count ? `${entry.skip_count} skip ${skipNoun(entry.label)}` : undefined}
                barColor={`var(--color-stage-${(index % 8) + 1})`}
                explain={{ what: `${entry.label} count`, params: withField(explainParams, `flow:${key}`) }}
              />
            </Fragment>
          )
        })}
        <span aria-hidden className="mx-1 w-px self-stretch bg-hairline" />
        <OnHoldCard count={onHoldCount} active={onHoldActive} onToggle={onToggleHold} />
      </div>
    </div>
  )
}
