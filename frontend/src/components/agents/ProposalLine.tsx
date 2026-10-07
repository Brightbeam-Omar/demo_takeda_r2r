import { Link } from 'react-router-dom'
import type { ProposalStatus } from '../../api/agents'
import type { RowDetail } from '../../api/queries'
import { ProposalPill } from './ProposalPill'

/**
 * The proposal-status line of the batch drawer's summary (F12-FR-13): the newest agent proposal for the batch, with a
 * link to it. A batch that is an air gap without one says so; every other batch shows nothing.
 */
export function ProposalLine({ detail }: { detail: Pick<RowDetail, 'proposal' | 'air_gap'> }) {
  const proposal = detail.proposal
  if (!proposal && !detail.air_gap) return null
  return (
    <p className="flex flex-wrap items-center gap-x-2 text-[13px]" data-testid="proposal-line">
      <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Agent proposal</span>
      {proposal ? (
        <>
          <ProposalPill status={proposal.status as ProposalStatus} />
          <Link to={`/agents/proposals/${proposal.id}`} className="text-accent hover:underline">
            View ↗
          </Link>
        </>
      ) : (
        <>
          <span className="text-slate-600">None yet</span>
          <Link to="/agents" className="text-accent hover:underline">
            Run the air-gap agent ↗
          </Link>
        </>
      )}
    </p>
  )
}
