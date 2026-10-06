import { useMemo, useState } from 'react'
import { usePipelineRuns, type PipelineRun } from '../../api/queries'
import { PageIntro } from '../../components/admin/PageIntro'
import { RunStepsWindow } from '../../components/admin/RunStepsWindow'
import { ErrorState, Skeleton } from '../../components/common/States'
import { DataTable, type Column } from '../../components/datatable/DataTable'
import { dagsterRunUrl } from '../../config'
import { formatDuration, formatRelative } from '../../lib/format'

const POLL_MS = 5000
const dash = (value: number | null | undefined) => (value === null || value === undefined ? '—' : String(value))

/** Sync Status (F21-FR-02): every pipeline run, newest first. A Run ID opens its per-step detail. */
export function SyncStatus() {
  const runs = usePipelineRuns(POLL_MS)
  const [open, setOpen] = useState<string | null>(null)

  const columns = useMemo<Column<PipelineRun>[]>(
    () => [
      {
        id: 'run',
        header: 'Run ID',
        text: (run) => run.pipeline_run_id.slice(0, 8),
        cell: (run, { hl }) => (
          <button
            type="button"
            data-testid="run-link"
            title={`Show the steps of run ${run.pipeline_run_id}`}
            className="font-mono text-accent underline decoration-dotted hover:text-indigo-900"
            onClick={() => setOpen(run.pipeline_run_id)}
          >
            {hl(run.pipeline_run_id.slice(0, 8))}
          </button>
        ),
      },
      {
        id: 'started',
        header: 'Started',
        text: (run) => (run.age_seconds === null ? '—' : formatRelative(run.age_seconds)),
        sortValue: (run) => run.age_seconds ?? Number.MAX_SAFE_INTEGER,
        cell: (run) => (run.age_seconds === null ? '—' : formatRelative(run.age_seconds)),
      },
      {
        id: 'duration',
        header: 'Duration',
        text: (run) => formatDuration(run.duration_ms),
        sortValue: (run) => run.duration_ms ?? -1,
        cell: (run) => formatDuration(run.duration_ms),
      },
      { id: 'files', header: 'Files', text: (run) => dash(run.files), sortValue: (run) => run.files ?? -1, cell: (run) => dash(run.files) },
      { id: 'inserted', header: 'Inserted', text: (run) => dash(run.inserted), sortValue: (run) => run.inserted ?? -1, cell: (run) => dash(run.inserted) },
      { id: 'total', header: 'Total', text: (run) => dash(run.total), sortValue: (run) => run.total ?? -1, cell: (run) => dash(run.total) },
      { id: 'skipped', header: 'Skipped', text: (run) => dash(run.skipped), sortValue: (run) => run.skipped ?? -1, cell: (run) => dash(run.skipped) },
      {
        id: 'status',
        header: 'Status',
        text: (run) => (run.status === 'ok' ? 'OK' : `FAILED ${run.failed_step ?? ''}`.trim()),
        cell: (run) =>
          run.status === 'ok' ? (
            <span data-testid="run-status" className="rounded-pill bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
              OK
            </span>
          ) : (
            <span data-testid="run-status" className="inline-flex flex-col">
              <span className="w-fit rounded-pill bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700">FAILED</span>
              <span className="mt-0.5 font-mono text-[11px] text-red-700">{run.failed_step}</span>
            </span>
          ),
      },
      {
        id: 'dagster',
        header: 'Dagster',
        text: () => '',
        cell: (run) => (
          <a
            href={dagsterRunUrl(run.pipeline_run_id)}
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline"
            aria-label={`Open run ${run.pipeline_run_id.slice(0, 8)} in Dagster`}
          >
            Open in Dagster ↗
          </a>
        ),
      },
    ],
    [],
  )

  return (
    <main className="flex-1 space-y-3 overflow-auto p-6 pb-20" data-testid="sync-status-page">
      <PageIntro
        subtitle="History of every pipeline run — click a Run ID to see per-step detail"
        clockNote="Started shows how long ago the run began on the demo clock. The demo clock only moves when the scenario moves it, so a run keeps its age until then."
      />
      {runs.isError && !runs.data ? <ErrorState what="the pipeline runs" error={runs.error} onRetry={() => void runs.refetch()} /> : null}
      {!runs.data && runs.isPending ? <Skeleton label="pipeline runs" height="h-64" /> : null}
      {runs.data ? (
        <DataTable
          rows={runs.data}
          columns={columns}
          rowKey={(run) => run.pipeline_run_id}
          exportName="pipeline-runs"
          unit={['run', 'runs']}
          empty="No pipeline run has been published yet."
          defaultPageSize={25}
          columnsKey="sync-status"
          rowTestId="run-row"
          ariaLabel="Pipeline runs"
          headerFilters={false}
          stickyFirst={false}
          toolbarExtra={
            <button
              type="button"
              className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400"
              onClick={() => void runs.refetch()}
            >
              Refresh
            </button>
          }
        />
      ) : null}
      {open ? <RunStepsWindow runId={open} onClose={() => setOpen(null)} /> : null}
    </main>
  )
}
