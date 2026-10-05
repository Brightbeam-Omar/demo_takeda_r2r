interface Props {
  count: number
  active: boolean
  onToggle: () => void
}

/** The On Hold card (amber): batches frozen in the ERP. It toggles the ON HOLD tag. */
export function OnHoldCard({ count, active, onToggle }: Props) {
  return (
    <button
      type="button"
      data-testid="flow-on_hold"
      aria-pressed={active}
      onClick={onToggle}
      className={`min-w-[92px] flex-1 rounded-card border border-amber-300 bg-amber-50 px-2.5 py-2 text-left hover:shadow ${active ? 'ring-2 ring-accent' : ''}`}
    >
      <div className="text-[11px] font-semibold tracking-wider text-amber-800 uppercase">⚠</div>
      <div className="text-sm font-semibold text-amber-900">On Hold</div>
      <div className="text-2xl font-semibold tabular-nums">{count}</div>
      <div className="text-xs text-amber-800">Frozen batches</div>
    </button>
  )
}
