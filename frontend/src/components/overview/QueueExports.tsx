import { useState } from 'react'
import { apiBlob } from '../../api/client'
import { saveBlob } from '../../lib/download'
import { useToast } from '../common/Toasts'

const BUTTON = 'rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400 disabled:opacity-50'

const EXPORTS = [
  { label: 'Export Sampling Plan', path: '/export/sampling-plan.csv', file: 'sampling-plan.csv' },
  { label: 'Export QC Testing Queue', path: '/export/qc-queue.csv', file: 'qc-testing-queue.csv' },
] as const

/**
 * `↓ Export Sampling Plan` and `↓ Export QC Testing Queue` (F18-FR-07). The server builds them with the
 * Overview filters; the persona header travels because the file is fetched, not linked.
 */
export function QueueExports({ params }: { params: URLSearchParams }) {
  const { notify } = useToast()
  const [busy, setBusy] = useState<string | null>(null)
  const download = async (item: (typeof EXPORTS)[number]) => {
    setBusy(item.path)
    try {
      saveBlob(await apiBlob(item.path, params), item.file)
    } catch (error) {
      notify(`Export failed: ${(error as Error).message}`, 'error')
    } finally {
      setBusy(null)
    }
  }
  return (
    <>
      {EXPORTS.map((item) => (
        <button key={item.path} type="button" disabled={busy !== null} className={BUTTON} onClick={() => void download(item)}>
          ↓ {item.label}
        </button>
      ))}
    </>
  )
}
