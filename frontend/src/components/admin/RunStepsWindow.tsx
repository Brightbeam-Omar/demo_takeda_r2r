import { usePipelineRunSteps } from '../../api/queries'
import { Modal } from '../common/Modal'
import { ErrorState, Skeleton } from '../common/States'
import { formatDuration } from '../../lib/format'

const TONE: Record<string, string> = {
  success: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}

/** The per-step rows of one pipeline run (F21-FR-02): step, status, duration, rows, error. */
export function RunStepsWindow({ runId, onClose }: { runId: string; onClose: () => void }) {
  const steps = usePipelineRunSteps(runId)
  return (
    <Modal
      open
      onClose={onClose}
      title={`Run ${runId.slice(0, 8)} — steps`}
      description={<span className="font-mono text-xs">{runId}</span>}
      testId="run-steps-window"
    >
      {steps.isError ? <ErrorState what="the run's steps" error={steps.error} onRetry={() => void steps.refetch()} /> : null}
      {steps.isPending ? <Skeleton label="steps" height="h-32" /> : null}
      {steps.data ? (
        <table className="w-full text-left text-[13px]" data-testid="run-steps">
          <thead className="text-[11px] tracking-wider text-ink-2 uppercase">
            <tr>
              <th className="py-1.5 font-semibold">Step</th>
              <th className="font-semibold">Status</th>
              <th className="font-semibold">Duration</th>
              <th className="font-semibold">Rows</th>
              <th className="font-semibold">Error</th>
            </tr>
          </thead>
          <tbody>
            {steps.data.steps.map((step) => (
              <tr key={step.step} data-testid="run-step" className="border-t border-hairline align-top">
                <td className="py-1.5 font-mono">{step.step}</td>
                <td>
                  <span className={`rounded-pill px-2 py-0.5 ${TONE[step.status] ?? ''}`}>{step.status}</span>
                </td>
                <td>{formatDuration(step.duration_ms)}</td>
                <td>{step.rows ?? '—'}</td>
                <td className="max-w-80 break-words whitespace-normal text-red-700">{step.error ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </Modal>
  )
}
