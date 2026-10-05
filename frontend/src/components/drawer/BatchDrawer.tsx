import * as Dialog from '@radix-ui/react-dialog'
import { useClock, useReference, useRowDetail } from '../../api/queries'
import { ExplainPopover } from '../explain/ExplainPopover'
import { Skeleton } from '../common/States'
import { StageChip, TagChips } from '../table/cells'
import { READ_ONLY_HINT } from '../../lib/roles'
import { DrawerSection, HumanInputSection, PlanSection, QualitySection, SourceRefs } from './Sections'
import { Comments } from './Comments'
import { StatusForm } from './StatusForm'
import { SiblingLots, StageTimeline } from './Timeline'

interface Props {
  rowKey: string | null
  onOpenRow: (rowKey: string | null) => void
  canEdit: boolean
  onEdit: (rowKey: string) => void
}

/** F11-FR-01. A right-hand drawer (560 px) for one lot; it loads the row by itself (OQ-072). */
export function BatchDrawer({ rowKey, onOpenRow, canEdit, onEdit }: Props) {
  const detail = useRowDetail(rowKey)
  const reference = useReference()
  const clock = useClock()
  const stages = reference.data?.stages ?? []
  const stageLabel = (key: string) => String(stages.find((stage) => stage.stage_key === key)?.label ?? key)
  const stageIndex = stages.findIndex((stage) => stage.stage_key === detail.data?.stage_key)
  const data = detail.data

  return (
    <Dialog.Root open={rowKey !== null} onOpenChange={(open) => !open && onOpenRow(null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/30" />
        <Dialog.Content
          aria-describedby={undefined}
          data-testid="batch-drawer"
          className="fixed inset-y-0 right-0 z-50 flex w-[560px] max-w-full flex-col overflow-hidden bg-white shadow-2xl"
        >
          <div className="flex items-start justify-between gap-3 px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="truncate text-lg font-semibold text-slate-900">
                {data ? `${data.material_no} · ${data.material_desc ?? ''}` : 'Batch'}
              </Dialog.Title>
              {data ? (
                <>
                  <p className="text-[13px] text-slate-600">
                    Batch {data.batch_no} · lot {data.inspection_lot_no} ({data.lot_type === '01' ? 'initial' : 're-evaluation'})
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[13px]">
                    <StageChip label={data.stage_label} index={stageIndex < 0 ? 0 : stageIndex} />
                    <ExplainPopover
                      what="stage"
                      path={`/rows/${encodeURIComponent(data.row_key)}/explain`}
                      params={new URLSearchParams({ field: 'stage' })}
                    />
                    <TagChips flags={data.flags} />
                  </div>
                </>
              ) : null}
            </div>
            <Dialog.Close
              aria-label="Close drawer"
              className="rounded-chip px-2 py-1 text-slate-500 hover:bg-slate-100"
            >
              ✕
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-auto">
            {detail.isPending && rowKey ? (
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
                <DrawerSection title="Timeline">
                  <StageTimeline detail={data} today={clock.data?.today_local ?? ''} stageLabel={stageLabel} />
                  {data.siblings.length > 0 ? (
                    <div className="mt-4">
                      <h4 className="mb-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                        Lots of this batch
                      </h4>
                      <SiblingLots detail={data} stageLabel={stageLabel} onOpen={onOpenRow} />
                    </div>
                  ) : null}
                </DrawerSection>
                <DrawerSection
                  title="Plan"
                  aside={
                    <button
                      type="button"
                      disabled={!canEdit}
                      title={canEdit ? 'Adjust need-by' : READ_ONLY_HINT}
                      className="rounded-chip border border-slate-300 px-2.5 py-1 text-xs enabled:hover:bg-slate-50 disabled:opacity-40"
                      onClick={() => onEdit(data.row_key)}
                    >
                      ✎ Edit need-by
                    </button>
                  }
                >
                  <PlanSection detail={data} />
                </DrawerSection>
                <DrawerSection title="Quality">
                  <QualitySection detail={data} />
                </DrawerSection>
                <DrawerSection title="Human input">
                  <StatusForm detail={data} />
                  <div className="mt-4">
                    <HumanInputSection detail={data} />
                  </div>
                </DrawerSection>
                <DrawerSection title="Comments">
                  <Comments detail={data} />
                </DrawerSection>
                <DrawerSection title="Source refs">
                  <SourceRefs detail={data} />
                </DrawerSection>
              </>
            ) : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
