import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { STATUSES, type ProposalListing, type ProposalStatus, type ProposalSummary } from '../../api/agents'
import { formatClock } from '../../lib/format'
import { DataTable, type Column } from '../datatable/DataTable'
import { PriorityChip, ProposalPill, STATUS_LABEL } from './ProposalPill'

export type Tab = ProposalStatus | 'all'
const TABS: Tab[] = ['all', ...STATUSES.filter((status) => status !== 'approved')]

interface Props {
  listing: ProposalListing
  tab: Tab
  onTab: (tab: Tab) => void
  timezone: string
}

const ACTION: Record<string, string> = {
  post_usage_decision: 'Post usage decision',
  investigate_deviation_first: 'Investigate deviation first',
  check_interface: 'Check interface',
}

/** The proposals inbox: status tabs with counts, and the list (F12-FR-12 b). A row opens the proposal. */
export function Inbox({ listing, tab, onTab, timezone }: Props) {
  const navigate = useNavigate()
  const total = Object.values(listing.counts).reduce((a, b) => a + b, 0)
  const columns = useMemo<Column<ProposalSummary>[]>(
    () => [
      { id: 'id', header: '#', text: (p) => String(p.id), sortValue: (p) => p.id, cell: (p) => <span className="font-mono">#{p.id}</span> },
      { id: 'batch', header: 'Batch', text: (p) => p.batch_no ?? '', cell: (p) => <span className="font-medium">{p.batch_no ?? '—'}</span> },
      { id: 'title', header: 'Ticket', text: (p) => p.title ?? p.error ?? '', cell: (p) => <span className="line-clamp-1">{p.title ?? p.error ?? '—'}</span> },
      { id: 'priority', header: 'Priority', text: (p) => p.priority ?? '', cell: (p) => <PriorityChip priority={p.priority} /> },
      { id: 'status', header: 'Status', text: (p) => STATUS_LABEL[p.status], cell: (p) => <ProposalPill status={p.status} /> },
      { id: 'hours', header: 'Hours in gap', text: (p) => String(p.hours_in_gap ?? ''), sortValue: (p) => p.hours_in_gap ?? -1, cell: (p) => (p.hours_in_gap === null ? '—' : `${p.hours_in_gap} h`) },
      { id: 'action', header: 'Recommended', text: (p) => ACTION[p.recommended_action ?? ''] ?? '', cell: (p) => ACTION[p.recommended_action ?? ''] ?? '—' },
      { id: 'created', header: 'Created', text: (p) => formatClock(p.created_at, timezone), sortValue: (p) => p.created_at, cell: (p) => formatClock(p.created_at, timezone) },
      {
        id: 'trace',
        header: 'Trace',
        text: (p) => p.trace_id ?? '',
        cell: (p) =>
          p.trace_id ? (
            <Link to={`/agents/traces/${p.trace_id}`} className="font-mono text-accent hover:underline" onClick={(event) => event.stopPropagation()}>
              {p.trace_id}
            </Link>
          ) : (
            '—'
          ),
      },
    ],
    [timezone],
  )
  return (
    <section aria-label="Proposals" data-testid="inbox">
      <h2 className="mb-2 text-base font-semibold text-ink">Proposals</h2>
      <div role="tablist" aria-label="Proposal status" className="mb-3 flex flex-wrap gap-2">
        {TABS.map((name) => {
          const count = name === 'all' ? total : listing.counts[name]
          const selected = tab === name
          return (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={selected}
              data-tab={name}
              className={`rounded-pill border px-3 py-1 text-sm ${selected ? 'border-accent bg-accent-tint text-accent' : 'border-hairline bg-white text-ink-2 hover:border-slate-400'}`}
              onClick={() => onTab(name)}
            >
              {name === 'all' ? 'All' : STATUS_LABEL[name]} <span className="ml-1 font-semibold">{count}</span>
            </button>
          )
        })}
      </div>
      <DataTable
        rows={listing.rows}
        columns={columns}
        rowKey={(p) => String(p.id)}
        exportName="proposals"
        unit={['proposal', 'proposals']}
        empty={tab === 'all' ? 'No proposals yet. Run the agent to draft one for each air-gap batch.' : 'No proposals with this status.'}
        rowTestId="proposal-row"
        onRowOpen={(p) => void navigate(`/agents/proposals/${p.id}`)}
        compact
      />
    </section>
  )
}
