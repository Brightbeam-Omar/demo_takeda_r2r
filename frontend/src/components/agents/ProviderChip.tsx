/** Where the model's answers came from: recorded ones (replay) or a live call (F14-FR-17, OQ-172). */
export function ProviderChip({ provider, modelId }: { provider: string | null; modelId: string | null }) {
  if (!provider) return null
  const replay = provider === 'replay'
  const label = replay ? `Replay · recorded from ${modelId ?? 'a recording'}` : `Live · ${modelId ?? provider}`
  return (
    <span
      data-testid="provider-chip"
      data-provider={replay ? 'replay' : 'live'}
      title={replay ? 'The answers are replayed from a recording; no model is called.' : 'The model is called live.'}
      className={`rounded-chip border px-1.5 py-px text-[11px] font-semibold ${replay ? 'border-sky-200 bg-sky-50 text-sky-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}
    >
      {label}
    </span>
  )
}
