import { useTerms } from '../../hooks/useTerms'
import { formatDate } from '../../lib/format'
import { inboundState } from '../../lib/windows'
import { Dot } from '../overview/cells'
import { BatchWindowShell, Heading, SummaryPanel, materialLine } from './BatchWindowShell'

interface Props {
  rowKey: string
  onClose: () => void
}

/** W2 Inbound (F19): the inbound check of one lot with its sub-checks and the overall verdict. */
export function InboundWindow({ rowKey, onClose }: Props) {
  const terms = useTerms()
  return (
    <BatchWindowShell
      rowKey={rowKey}
      onClose={onClose}
      testId="inbound-window"
      title={(detail) => `Inbound — ${detail.batch_no}`}
    >
      {(detail) => {
        const check = detail.inbound_check
        const state = inboundState(check)
        return (
          <div className="space-y-1">
            <SummaryPanel
              items={[
                [
                  'Result',
                  <span key="result" className="inline-flex items-center gap-2 font-medium" data-testid="inbound-result">
                    <Dot colour={state.colour} what="Inbound check" />
                    {state.label}
                  </span>,
                ],
                ['Material', materialLine(detail)],
              ]}
            />
            {check ? (
              <>
                <Heading>Inbound check</Heading>
                <dl className="grid grid-cols-[12rem_1fr] gap-y-1 text-[13px]">
                  <dt className="text-slate-500">{terms.erp} lot number</dt>
                  <dd>{check.prueflos}</dd>
                  <dt className="text-slate-500">Check deadline</dt>
                  <dd>{formatDate(check.deadline)}</dd>
                  {check.failed_count > 0 && (
                    <>
                      <dt className="text-slate-500">Failed checks</dt>
                      <dd className="font-semibold text-red-700" data-testid="failed-checks">
                        Failed checks: {check.failed_count}
                      </dd>
                    </>
                  )}
                </dl>
                <Heading>Sub-checks</Heading>
                {check.items.length === 0 ? (
                  <p className="text-[13px] text-slate-500">No sub-checks recorded yet.</p>
                ) : (
                  <ul className="divide-y divide-slate-100 rounded-card border border-slate-200 text-[13px]" data-testid="inbound-items">
                    {check.items.map((item) => (
                      <li key={item.seq} className="flex items-center justify-between px-3 py-1.5" data-outcome={item.outcome}>
                        <span>{item.check_label}</span>
                        <span className={item.outcome === 'FAIL' ? 'font-semibold text-red-700' : 'text-slate-700'}>{item.outcome === 'PENDING' ? 'Pending' : item.outcome}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <Heading>Check results</Heading>
                <p className="text-[13px] font-medium" data-testid="inbound-verdict">
                  {state.verdict}
                </p>
              </>
            ) : (
              <p className="pt-3 text-[13px] text-slate-500" data-testid="inbound-none">
                No inbound check recorded.
              </p>
            )}
          </div>
        )
      }}
    </BatchWindowShell>
  )
}
