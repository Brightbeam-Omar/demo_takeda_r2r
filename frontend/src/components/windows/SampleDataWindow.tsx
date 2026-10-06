import { useState } from 'react'
import type { RowDetail } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import { formatDate, humanize } from '../../lib/format'
import { SAMPLE_PILLS, sampleCounts, samplePill, type SamplePill } from '../../lib/windows'
import { DataTable, type Column } from '../datatable/DataTable'
import { useToast } from '../common/Toasts'
import { BatchWindowShell } from './BatchWindowShell'

interface Props {
  rowKey: string
  onClose: () => void
}

type Sample = RowDetail['samples'][number]

const CHIP: Record<string, string> = {
  received: 'border-sky-200 bg-sky-50 text-sky-800',
  approved: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  rejected: 'border-red-200 bg-red-50 text-red-800',
}

/** W5 Sample Data (F19): every LIMS sample of the lot; a click on the Sample ID copies it. */
export function SampleDataWindow({ rowKey, onClose }: Props) {
  const terms = useTerms()
  return (
    <BatchWindowShell
      rowKey={rowKey}
      onClose={onClose}
      testId="samples-window"
      title={(detail) => `Sample Data — ${detail.batch_no} (${detail.samples.length} ${detail.samples.length === 1 ? 'sample' : 'samples'})`}
      description={`${terms.lims} sample records for this batch. Click a Sample ID to copy it.`}
    >
      {(detail) => <SampleBody samples={detail.samples} />}
    </BatchWindowShell>
  )
}

function SampleBody({ samples }: { samples: Sample[] }) {
  const { notify } = useToast()
  const [pill, setPill] = useState<SamplePill>('all')
  const counts = sampleCounts(samples)
  const pills = SAMPLE_PILLS.filter((name) => name !== 'rejected' || counts.rejected > 0)
  const shown = samples.filter((sample) => pill === 'all' || samplePill(sample.status) === pill)
  const copy = (id: string) => {
    void navigator.clipboard.writeText(id).then(() => notify('Copied'))
  }
  const columns: Column<Sample>[] = [
    {
      id: 'sample_id',
      header: 'Sample ID',
      text: (s) => s.sample_id,
      cell: (s) => (
        <button type="button" title="Copy the Sample ID" className="font-mono font-medium text-accent hover:underline" onClick={() => copy(s.sample_id)}>
          {s.sample_id}
        </button>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      text: (s) => humanize(samplePill(s.status)),
      cell: (s) => (
        <span className={`rounded-pill border px-2 py-0.5 text-xs font-semibold ${CHIP[samplePill(s.status)]}`}>{humanize(samplePill(s.status))}</span>
      ),
    },
    { id: 'collected', header: 'Collected', text: (s) => formatDate(s.collected_date), sortValue: (s) => s.collected_date ?? '', cell: (s) => formatDate(s.collected_date) },
    { id: 'approved', header: 'Approved', text: (s) => formatDate(s.approved_at), sortValue: (s) => s.approved_at ?? '', cell: (s) => formatDate(s.approved_at) },
  ]
  return (
    <div className="space-y-3">
      <div role="group" aria-label="Sample status" className="flex gap-1.5">
        {pills.map((name) => (
          <button
            key={name}
            type="button"
            aria-pressed={pill === name}
            className={`rounded-pill border px-3 py-1 text-xs font-semibold ${pill === name ? 'border-accent bg-accent-tint text-accent' : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'}`}
            onClick={() => setPill(name)}
          >
            {humanize(name)} ({counts[name]})
          </button>
        ))}
      </div>
      <DataTable
        rows={shown}
        columns={columns}
        exportName="samples"
        rowKey={(s) => s.sample_id}
        unit={['sample', 'samples']}
        headerFilters={false}
        stickyFirst={false}
        defaultPageSize={25}
        compact
        ariaLabel="Samples"
      />
    </div>
  )
}
