interface Props {
  count: number
  caption: string
  onOpen: () => void
}

/** Stage 0 (F17-FR-04): open PO lines, a pre-batch grain. Dashed, and never added to the pipeline total. */
export function ExpectedDeliveryCard({ count, caption, onOpen }: Props) {
  return (
    <div className="flex min-w-[92px] flex-1">
      <button
        type="button"
        data-testid="flow-expected-delivery"
        onClick={onOpen}
        className="flex h-full w-full flex-col justify-start rounded-card border border-dashed border-ink-3 bg-white px-2.5 py-2 text-left hover:shadow"
      >
        <div className="text-[11px] font-semibold tracking-wider text-ink-2 uppercase">Stage 0</div>
        <div className="text-sm leading-tight font-semibold text-ink">Expected Delivery</div>
        <div className="text-2xl font-semibold tabular-nums" data-testid="expected-delivery-count">
          {count}
        </div>
        <div className="text-xs leading-tight text-ink-2">{caption}</div>
      </button>
    </div>
  )
}
