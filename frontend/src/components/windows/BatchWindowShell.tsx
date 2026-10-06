import type { ReactNode } from 'react'
import { useRowDetail, type RowDetail } from '../../api/queries'
import { Modal } from '../common/Modal'
import { Skeleton } from '../common/States'

interface Props {
  rowKey: string
  onClose: () => void
  /** The window title for a loaded row, e.g. `Inbound — B2077`. */
  title: (detail: RowDetail) => string
  testId: string
  description?: ReactNode
  children: (detail: RowDetail) => ReactNode
}

/** The shared frame of the five batch windows (05 v2 section 5): loads the row, then draws the window body. */
export function BatchWindowShell({ rowKey, onClose, title, testId, description, children }: Props) {
  const detail = useRowDetail(rowKey)
  const data = detail.data
  return (
    <Modal
      open
      size="window"
      onClose={onClose}
      testId={testId}
      title={data ? title(data) : 'Loading…'}
      description={description}
    >
      {detail.isError ? (
        <p role="alert" className="rounded-card border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Batch not found: {rowKey}
        </p>
      ) : data ? (
        children(data)
      ) : (
        <Skeleton label="batch" height="h-40" />
      )}
    </Modal>
  )
}

/** The grey summary panel at the top of a window: label over value pairs. */
export function SummaryPanel({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 rounded-card bg-panel p-4 text-[13px]">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{label}</dt>
          <dd className="mt-0.5 text-slate-900">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Heading({ children }: { children: ReactNode }) {
  return <h3 className="mt-5 mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">{children}</h3>
}

export const materialLine = (detail: RowDetail) => `${detail.material_no} · ${detail.material_desc ?? ''}`.trim()
