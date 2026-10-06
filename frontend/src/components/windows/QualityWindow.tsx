import { useMemo, useState } from 'react'
import type { RowDetail } from '../../api/queries'
import { formatDate, humanize } from '../../lib/format'
import { Dot } from '../overview/cells'
import { BatchWindowShell, SummaryPanel, materialLine } from './BatchWindowShell'

interface Props {
  rowKey: string
  onClose: () => void
}

type Deviation = RowDetail['deviations'][number]
type Change = RowDetail['changes'][number]
type Tab = 'open' | 'closed' | 'changes'
const SEVERITIES = ['all', 'major', 'moderate', 'minor'] as const

const SEVERITY_TONE: Record<string, string> = {
  major: 'border-red-200 bg-red-50 text-red-800',
  moderate: 'border-amber-200 bg-amber-50 text-amber-800',
  minor: 'border-slate-200 bg-slate-50 text-slate-700',
}
const STATUS_TONE: Record<string, string> = {
  open: 'border-red-200 bg-white text-red-700',
  closed: 'border-slate-200 bg-white text-slate-600',
  approved: 'border-emerald-200 bg-white text-emerald-700',
  cancelled: 'border-slate-200 bg-white text-slate-500',
}

const Badge = ({ tone, children, testId }: { tone: string; children: string; testId?: string }) => (
  <span data-testid={testId} className={`rounded-pill border px-2 py-0.5 text-xs font-semibold ${tone}`}>
    {children}
  </span>
)

function Field({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <p>
      <span className="text-slate-500">{label}: </span>
      {value}
    </p>
  )
}

function DeviationCard({ deviation, expanded }: { deviation: Deviation; expanded: boolean }) {
  return (
    <li className="rounded-card border border-slate-200 p-3 text-[13px]" data-testid="deviation-card" data-severity={deviation.severity}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">Ref: {deviation.deviation_no}</span>
        <Badge tone={SEVERITY_TONE[deviation.severity ?? 'minor'] ?? SEVERITY_TONE.minor!} testId="severity-badge">
          {humanize(deviation.severity ?? 'minor')}
        </Badge>
        <Badge tone={STATUS_TONE[deviation.status ?? 'open'] ?? STATUS_TONE.closed!}>{humanize(deviation.status ?? '')}</Badge>
        <span className="ml-auto text-slate-500">Raised {formatDate(deviation.opened_on)}</span>
      </div>
      <p className="mt-1.5 font-medium">{deviation.title}</p>
      {expanded && (
        <div className="mt-1.5 space-y-0.5 text-slate-700">
          <Field label="Causal Factor" value={deviation.causal_factor} />
          <Field label="Root Cause" value={deviation.root_cause_category} />
          <Field label="Description" value={deviation.description} />
          <Field label="Investigation Summary" value={deviation.investigation_summary} />
        </div>
      )}
    </li>
  )
}

function ChangeCard({ change }: { change: Change }) {
  return (
    <li className="rounded-card border border-slate-200 p-3 text-[13px]" data-testid="change-card">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">Ref: {change.cc_no}</span>
        <Badge tone={STATUS_TONE[change.status ?? 'open'] ?? STATUS_TONE.closed!}>{humanize(change.status ?? '')}</Badge>
        {change.effective_on && <span className="ml-auto text-slate-500">Effective {formatDate(change.effective_on)}</span>}
      </div>
      <p className="mt-1.5 font-medium">{change.title}</p>
      <p className="mt-1 text-slate-700">
        <span className="text-slate-500">{change.current_state}</span> → {change.proposed_state}
      </p>
    </li>
  )
}

/** W3 Quality (F19): open and closed deviations and the change controls of the batch. */
export function QualityWindow({ rowKey, onClose }: Props) {
  return (
    <BatchWindowShell rowKey={rowKey} onClose={onClose} testId="quality-window" title={(detail) => `Quality — ${detail.batch_no}`}>
      {(detail) => <QualityBody detail={detail} />}
    </BatchWindowShell>
  )
}

function QualityBody({ detail }: { detail: RowDetail }) {
  const [tab, setTab] = useState<Tab>('open')
  const [severity, setSeverity] = useState<(typeof SEVERITIES)[number]>('all')
  const [newestFirst, setNewestFirst] = useState(true)
  const [expanded, setExpanded] = useState(true)
  const open = detail.deviations.filter((d) => d.status === 'open')
  const closed = detail.deviations.filter((d) => d.status !== 'open')
  const rating = detail.deviation_light ?? 'grey'
  const shown = useMemo(() => {
    const pool = (tab === 'open' ? open : closed).filter((d) => severity === 'all' || d.severity === severity)
    return [...pool].sort((a, b) => {
      const order = String(b.opened_on ?? '').localeCompare(String(a.opened_on ?? '')) || b.deviation_no.localeCompare(a.deviation_no)
      return newestFirst ? order : -order
    })
  }, [tab, open, closed, severity, newestFirst])
  const tabs: [Tab, string, number][] = [
    ['open', 'Open Deviations', open.length],
    ['closed', 'Closed / Cancelled', closed.length],
    ['changes', 'Changes', detail.changes.length],
  ]
  return (
    <div className="space-y-3">
      <SummaryPanel
        items={[
          [
            'Rating',
            <span key="rating" className="inline-flex items-center gap-2 font-medium" data-testid="quality-rating">
              <Dot colour={rating} what="Deviations" />
              {humanize(rating)}, {open.length} open {open.length === 1 ? 'deviation' : 'deviations'}
            </span>,
          ],
          ['Material', materialLine(detail)],
        ]}
      />
      <div role="tablist" aria-label="Quality" className="flex gap-1 border-b border-slate-200">
        {tabs.map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`-mb-px border-b-2 px-3 py-1.5 text-[13px] font-medium ${tab === id ? 'border-accent text-accent' : 'border-transparent text-slate-600 hover:text-slate-900'}`}
            onClick={() => setTab(id)}
          >
            {label} ({count})
          </button>
        ))}
      </div>
      {tab !== 'changes' && (
        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          <div role="group" aria-label="Severity" className="flex gap-1">
            {SEVERITIES.map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={severity === value}
                className={`rounded-pill border px-2.5 py-0.5 text-xs font-semibold ${severity === value ? 'border-accent bg-accent-tint text-accent' : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'}`}
                onClick={() => setSeverity(value)}
              >
                {value === 'all' ? 'ALL' : humanize(value)}
              </button>
            ))}
          </div>
          <select
            aria-label="Sort"
            className="ml-auto rounded-chip border border-slate-300 px-2 py-1"
            value={newestFirst ? 'newest' : 'oldest'}
            onChange={(event) => setNewestFirst(event.target.value === 'newest')}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
          <button type="button" className="rounded-chip px-2 py-1 text-accent hover:bg-accent-tint" onClick={() => setExpanded(true)}>
            Expand all
          </button>
          <button type="button" className="rounded-chip px-2 py-1 text-accent hover:bg-accent-tint" onClick={() => setExpanded(false)}>
            Collapse all
          </button>
        </div>
      )}
      <ul className="space-y-2" data-testid="quality-list">
        {tab === 'changes'
          ? detail.changes.map((change) => <ChangeCard key={change.cc_no} change={change} />)
          : shown.map((deviation) => <DeviationCard key={deviation.deviation_no} deviation={deviation} expanded={expanded} />)}
      </ul>
      {(tab === 'changes' ? detail.changes.length === 0 : shown.length === 0) && (
        <p className="py-4 text-center text-[13px] text-slate-500">
          {tab === 'changes' ? 'No change controls linked to this batch.' : 'No deviations to show.'}
        </p>
      )}
    </div>
  )
}
