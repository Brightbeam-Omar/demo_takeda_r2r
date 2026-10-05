import type { Overview, Reference } from '../../api/queries'

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
}

export const MODE_CAPTION: Record<Overview['mode'], string> = {
  snapshot: 'snapshot',
  due_in_period: 'due in period',
}

/** F10-FR-07. One card per stage, plus Total and On Hold. A red outline marks a stage with late rows. */
export function FlowStrip({ entries, stages, mode, onHoldCount, activeStage, onHoldActive, onToggleStage, onToggleHold }: Props) {
  const total = entries.reduce((sum, entry) => sum + entry.count, 0)
  const sla = new Map(stages.map((stage) => [String(stage.stage_key), Number(stage.sla_days ?? 0)]))
  return (
    <div className="space-y-1">
      <p className="text-xs text-slate-500" data-testid="flow-caption">
        Counts: {MODE_CAPTION[mode]}
      </p>
      <div className="flex gap-2 overflow-x-auto pb-1">
        <div className="min-w-24 rounded-card border border-slate-200 bg-white px-3 py-2">
          <div className="text-xs text-slate-500">Total</div>
          <div className="text-xl font-semibold tabular-nums" data-testid="flow-total">
            {total}
          </div>
        </div>
        {entries.map((entry, index) => {
          const active = activeStage === entry.stage_key
          return (
            <button
              key={entry.stage_key}
              type="button"
              data-testid={`flow-${entry.stage_key}`}
              aria-pressed={active}
              onClick={() => onToggleStage(entry.stage_key)}
              style={{ borderTopColor: `var(--color-stage-${(index % 8) + 1})` }}
              className={`min-w-28 flex-1 rounded-card border border-t-4 bg-white px-3 py-2 text-left hover:shadow ${
                entry.breached ? 'border-red-500' : 'border-slate-200'
              } ${active ? 'ring-2 ring-indigo-600' : ''}`}
            >
              <div className="text-xs text-slate-600">{entry.label}</div>
              <div className="text-xl font-semibold tabular-nums">{entry.count}</div>
              {(sla.get(entry.stage_key) ?? 0) > 0 && (
                <div className="text-xs text-slate-500">SLA {sla.get(entry.stage_key)} d</div>
              )}
            </button>
          )
        })}
        <button
          type="button"
          data-testid="flow-on_hold"
          aria-pressed={onHoldActive}
          onClick={onToggleHold}
          className={`min-w-24 rounded-card border border-amber-300 bg-amber-50 px-3 py-2 text-left hover:shadow ${onHoldActive ? 'ring-2 ring-indigo-600' : ''}`}
        >
          <div className="text-xs text-amber-800">On Hold</div>
          <div className="text-xl font-semibold tabular-nums">{onHoldCount}</div>
        </button>
      </div>
    </div>
  )
}
