export type Tone = 'green' | 'amber' | 'red' | 'grey'

const BAR: Record<Tone, string> = {
  green: 'bg-emerald-500',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
  grey: 'bg-slate-300',
}

interface Props {
  label: string
  value: string
  note?: string
  tag?: string
  tone: Tone
  testId: string
  title?: string
}

/** One health card of the Webhook Sync Status page: a 4 px top bar in the tone, a label, a big number (F21-FR-03). */
export function HealthCard({ label, value, note, tag, tone, testId, title }: Props) {
  return (
    <div data-testid={testId} data-tone={tone} title={title} className="overflow-hidden rounded-card border border-hairline bg-white">
      <div className={`h-1 ${BAR[tone]}`} />
      <div className="p-3">
        <div className="flex items-center gap-2 text-[11px] font-semibold tracking-wider text-ink-2 uppercase">
          {label}
          {tag ? <span className="rounded-pill bg-panel px-1.5 py-0.5 text-[10px] whitespace-nowrap text-ink-2">{tag}</span> : null}
        </div>
        <div className="mt-1 text-2xl font-semibold text-ink" data-testid={`${testId}-value`}>
          {value}
        </div>
        {note ? <div className="text-xs text-ink-2">{note}</div> : null}
      </div>
    </div>
  )
}
