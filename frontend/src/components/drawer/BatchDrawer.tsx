import { useEffect } from 'react'
import { useClock, useReference, useRowDetail } from '../../api/queries'
import { useTerms } from '../../hooks/useTerms'
import type { WindowName } from '../../state/batch-view'
import { Skeleton } from '../common/States'
import { ExplainPopover } from '../explain/ExplainPopover'
import { rowTags } from '../overview/cells'
import { StageChip } from '../table/cells'
import { ProposalLine } from '../agents/ProposalLine'
import { DrawerSection, InboundSummary, NeedBySummary, OpenLink, QualitySummary, SamplesSummary, SourceRefs, StatusLogSummary } from './Sections'
import { ExportTimeline, HistorySummary, MilestoneDates, OtherLots, StageTimeline } from './Timeline'

interface Props {
  rowKey: string
  /** Swap the drawer to another lot of the batch. */
  onOpenRow: (rowKey: string) => void
  onClose: () => void
  onOpenWindow: (win: WindowName, rowKey: string) => void
}

/**
 * The batch's home (F19, OQ-116): a non-modal 560 px panel beside the table. Its top sections are the batch
 * history (summary, milestone dates, stage timeline, other lots, export); below them each summary section links
 * to its window. It loads the row by itself (OQ-072), so it opens even when the row is filtered out.
 */
export function BatchDrawer({ rowKey, onOpenRow, onClose, onOpenWindow }: Props) {
  const detail = useRowDetail(rowKey)
  const reference = useReference()
  const clock = useClock()
  const terms = useTerms()
  const stages = reference.data?.stages ?? []
  const stageLabel = (key: string) => String(stages.find((stage) => stage.stage_key === key)?.label ?? key)
  const stageIndex = stages.findIndex((stage) => stage.stage_key === detail.data?.stage_key)
  const data = detail.data
  const today = clock.data?.today_local ?? ''
  const open = (win: WindowName) => data && onOpenWindow(win, data.row_key)

  // Escape closes the drawer, unless a window is open on top of it (the window takes the key first).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return
      if (document.querySelector('[role="dialog"]')) return
      onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <aside
      aria-label="Batch drawer"
      data-testid="batch-drawer"
      className="flex w-[560px] max-w-[45vw] shrink-0 flex-col overflow-hidden border-l border-hairline bg-white"
    >
      <div className="flex items-start justify-between gap-3 px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-lg leading-tight font-semibold break-words text-slate-900">{data ? `${data.material_no} · ${data.material_desc ?? ''}` : 'Batch'}</h2>
          {data ? (
            <p className="text-[13px] text-slate-600">
              Batch {data.batch_no} · lot {data.inspection_lot_no} ({data.lot_type === '01' ? 'initial' : 're-evaluation'})
            </p>
          ) : null}
        </div>
        <button type="button" aria-label="Close drawer" className="rounded-chip px-2 py-1 text-slate-500 hover:bg-slate-100" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="flex-1 overflow-auto pb-24">
        {detail.isPending ? (
          <div className="p-5">
            <Skeleton label="batch" height="h-64" />
          </div>
        ) : null}
        {detail.isError ? (
          <p role="alert" className="m-5 rounded-card border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            Batch not found: {rowKey}
          </p>
        ) : null}
        {data ? (
          <>
            <DrawerSection title="Batch history">
              <HistorySummary
                detail={data}
                today={today}
                stageChip={
                  <>
                    <StageChip label={data.stage_label} index={stageIndex < 0 ? 0 : stageIndex} />
                    <ExplainPopover
                      what="stage"
                      path={`/rows/${encodeURIComponent(data.row_key)}/explain`}
                      params={new URLSearchParams({ field: 'stage' })}
                    />
                  </>
                }
                tags={rowTags(data, terms).map((tag) => (
                  <span key={tag.id} className={`rounded-chip border px-1.5 py-px text-[10px] font-semibold tracking-wide ${tag.off.split(' ').filter((name) => !name.startsWith('hover:')).join(' ')}`}>
                    {tag.label}
                  </span>
                ))}
              />
              <div className="mt-2 empty:hidden">
                <ProposalLine detail={data} />
              </div>
            </DrawerSection>
            <DrawerSection title="Milestone dates">
              <MilestoneDates detail={data} />
            </DrawerSection>
            <DrawerSection title="Stage timeline">
              <StageTimeline detail={data} today={today} stageLabel={stageLabel} />
            </DrawerSection>
            <DrawerSection title="Other lots of this batch" aside={<ExportTimeline detail={data} today={today} stageLabel={stageLabel} />}>
              <OtherLots detail={data} stageLabel={stageLabel} onOpen={onOpenRow} />
            </DrawerSection>
            <DrawerSection title="Quality" aside={<OpenLink label="Quality" win="quality" onOpen={open} />}>
              <QualitySummary detail={data} />
            </DrawerSection>
            <DrawerSection title="Inbound" aside={<OpenLink label="Inbound" win="inbound" onOpen={open} />}>
              <InboundSummary detail={data} />
            </DrawerSection>
            <DrawerSection title="Status log" aside={<OpenLink label="Status log" win="status" onOpen={open} />}>
              <StatusLogSummary detail={data} />
            </DrawerSection>
            <DrawerSection title="Samples" aside={<OpenLink label="Samples" win="samples" onOpen={open} />}>
              <SamplesSummary detail={data} />
            </DrawerSection>
            <DrawerSection title="Need-by" aside={<OpenLink label="Need-by" win="needby" onOpen={open} />}>
              <NeedBySummary detail={data} />
            </DrawerSection>
            <DrawerSection title="Source refs">
              <SourceRefs detail={data} />
            </DrawerSection>
          </>
        ) : null}
      </div>
    </aside>
  )
}
