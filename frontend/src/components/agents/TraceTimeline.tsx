import type { TraceStep } from '../../api/agents'

const TONE: Record<TraceStep['step_type'], string> = {
  input: 'bg-slate-100 text-slate-700',
  tool_call: 'bg-sky-50 text-sky-800',
  tool_result: 'bg-sky-50 text-sky-800',
  model_request: 'bg-violet-50 text-violet-800',
  model_response: 'bg-violet-50 text-violet-800',
  validation: 'bg-amber-50 text-amber-800',
  decision: 'bg-emerald-50 text-emerald-800',
  action: 'bg-emerald-100 text-emerald-900',
}

const LABEL: Record<TraceStep['step_type'], string> = {
  input: 'Input',
  tool_call: 'Tool call',
  tool_result: 'Tool result',
  model_request: 'Model request',
  model_response: 'Model response',
  validation: 'Validation',
  decision: 'Decision',
  action: 'Action',
}

const text = (value: unknown): string => (typeof value === 'string' ? value : JSON.stringify(value))

/** One line saying what the step was, from its payload. */
export function summarise(step: TraceStep): string {
  const p = step.payload ?? {}
  switch (step.step_type) {
    case 'input':
      return `${text(p.agent)} · batch ${text(p.batch_no)} · ${text(p.air_gap_hours)} h in the gap`
    case 'tool_call':
      return `${text(p.name)}(${Object.values((p.input ?? {}) as Record<string, unknown>).map(text).join(', ')}) → ${text(p.system)}`
    case 'tool_result':
      return `${text(p.name)} from ${text(p.system)}: ${p.is_error ? 'error' : 'ok'}`
    case 'model_request':
      return `Model call ${text(p.turn)} · ${text(p.model_id)}`
    case 'model_response': {
      if (p.error) return `Failed: ${text(p.message)}`
      const blocks = (p.content ?? []) as { type: string; name?: string }[]
      const uses = blocks.filter((b) => b.type === 'tool_use').map((b) => b.name)
      return `stop: ${text(p.stop_reason)}${uses.length ? ` · asks for ${uses.join(', ')}` : ''}${p.replayed ? ' · replayed' : ''}`
    }
    case 'validation': {
      const rules = (p.rules ?? []) as { id: string; passed: boolean }[]
      const failed = rules.filter((r) => !r.passed).map((r) => r.id)
      return p.passed ? `All ${rules.length} rules passed${p.trigger === 'approve' ? ' (checked again on approve)' : ''}` : `Failed: ${failed.join(', ') || 'schema'}${p.headline ? ` · ${text(p.headline)}` : ''}`
    }
    case 'decision':
      return `${text(p.outcome)}${p.by ? ` by ${text(p.by)}` : ''}${p.headline ? ` · ${text(p.headline)}` : ''}${p.reason ? ` · ${text(p.reason)}` : ''}`
    case 'action':
      return p.ticket_no ? `Ticket ${text(p.ticket_no)} created, email queued (${text(p.delivery)})` : `${text(p.type)}${p.proposal_id ? ` #${text(p.proposal_id)}` : ''}`
  }
}

/** A vertical timeline of the steps, each with its tokens and latency and an expandable payload (F12-FR-12 d). */
export function TraceTimeline({ steps }: { steps: TraceStep[] }) {
  return (
    <ol className="relative space-y-2 border-l-2 border-hairline pl-5" data-testid="trace-timeline">
      {steps.map((step) => (
        <li key={step.seq} data-testid="trace-step" data-step-type={step.step_type} className="relative">
          <span aria-hidden className="absolute top-3 -left-[27px] size-2.5 rounded-full border-2 border-white bg-slate-400" />
          <details className="rounded-card border border-hairline bg-white">
            <summary className="flex cursor-pointer items-center gap-3 px-3 py-2 text-[13px]">
              <span className="w-6 shrink-0 text-right font-mono text-ink-2">{step.seq}</span>
              <span className={`w-28 shrink-0 rounded-chip px-1.5 py-px text-center text-[11px] font-semibold ${TONE[step.step_type]}`}>{LABEL[step.step_type]}</span>
              <span className="min-w-0 flex-1 truncate">{summarise(step)}</span>
              <span className="shrink-0 font-mono text-xs text-ink-2">
                {step.tokens_in !== null ? `${step.tokens_in} in / ${step.tokens_out ?? 0} out` : ''}
                {step.latency_ms !== null ? ` ${step.latency_ms} ms` : ''}
              </span>
            </summary>
            <pre className="max-h-96 overflow-auto border-t border-hairline bg-panel p-3 font-mono text-xs whitespace-pre-wrap">{JSON.stringify(step.payload, null, 2)}</pre>
          </details>
        </li>
      ))}
    </ol>
  )
}
