import type { Overview, Reference } from '../../api/queries'
import { ExplainPopover } from '../explain/ExplainPopover'

type Entry = Overview['flow_strip'][number]

interface Props {
  entries: Entry[]
  stages: Reference['stages']
  mode: Overview['mode']
  onHoldCount: number
  activeStage: string | null
  onHoldActive: boolean
  onToggleStage: (stageKey: string) => void
  onToggleHold: () => void
  /** The filters behind the counts, without the stage filter, so a flow explanation matches the card. */
  explainParams?: URLSearchParams
}

function withField(base: URLSearchParams | undefined, field: string): URLSearchParams {
  const params = new URLSearchParams(base)
  params.set('field', field)
  return params
}

export const MODE_CAPTION: Record<Overview['mode'], string> = {
  snapshot: 'snapshot',
  due_in_period: 'due in period',
}

/** F10-FR-07. One card per stage, plus the open-pipeline total and On Hold. Late rows show as a small red count. */
export function FlowStrip({ entries, stages, mode, onHoldCount, activeStage, onHoldActive, onToggleStage, onToggleHold, explainParams }: Props) {
  const terminal = new Set(stages.filter((stage) => stage.terminal).map((stage) => String(stage.stage_key)))
  // Released lots have left the pipeline, so the total counts open rows only.
  const total = entries.filter((entry) => !terminal.has(entry.stage_key)).reduce((sum, entry) => sum + entry.count, 0)
  const sla = new Map(stages.map((stage) => [String(stage.stage_key), Number(stage.sla_days ?? 0)]))
  return (
    <div className="space-y-1">
      <p className="text-xs text-slate-500" data-testid="flow-caption">
        Counts: {MODE_CAPTION[mode]}
      </p>
      <div className="flex gap-2 overflow-x-auto pb-1">
        <div className="w-24 shrink-0 rounded-card border border-slate-200 bg-white px-2.5 py-2">
          <div className="text-xs text-slate-500">Open pipeline</div>
          <div className="text-xl font-semibold tabular-nums" data-testid="flow-total">
            {total}
          </div>
        </div>
        {entries.map((entry, index) => {
          const active = activeStage === entry.stage_key
          return (
            <div key={entry.stage_key} className="relative flex min-w-24 flex-1">
            <button
              type="button"
              data-testid={`flow-${entry.stage_key}`}
              aria-pressed={active}
              onClick={() => onToggleStage(entry.stage_key)}
              style={{ borderTopColor: `var(--color-stage-${(index % 8) + 1})` }}
              className={`w-full rounded-card border border-t-4 border-slate-200 bg-white px-2.5 py-2 text-left hover:shadow ${
                active ? 'ring-2 ring-indigo-600' : ''
              }`}
            >
              <div className="text-xs text-slate-600">{entry.label}</div>
              <div className="text-xl font-semibold tabular-nums">{entry.count}</div>
              <div className="flex h-4 items-center justify-between gap-1.5 text-xs whitespace-nowrap">
                <span className="text-slate-500">
                  {(sla.get(entry.stage_key) ?? 0) > 0 ? `SLA ${sla.get(entry.stage_key)} d` : ''}
                </span>
                {entry.late_count > 0 && (
                  <span className="font-semibold text-red-700" data-testid={`late-${entry.stage_key}`}>
                    {entry.late_count} late
                  </span>
                )}
              </div>
            </button>
            <span className="absolute top-1.5 right-1.5">
              <ExplainPopover
                what={`${entry.label} count`}
                path="/explain"
                params={withField(explainParams, `flow:${entry.stage_key}`)}
              />
            </span>
            </div>
          )
        })}
        <button
          type="button"
          data-testid="flow-on_hold"
          aria-pressed={onHoldActive}
          onClick={onToggleHold}
          className={`w-24 shrink-0 rounded-card border border-amber-300 bg-amber-50 px-2.5 py-2 text-left hover:shadow ${onHoldActive ? 'ring-2 ring-indigo-600' : ''}`}
        >
          <div className="text-xs text-amber-800">On Hold</div>
          <div className="text-xl font-semibold tabular-nums">{onHoldCount}</div>
        </button>
      </div>
    </div>
  )
}
