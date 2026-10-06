import { useBatchView } from '../../state/batch-view'
import { AdjustNeedsByWindow } from './AdjustNeedsByWindow'
import { InboundWindow } from './InboundWindow'
import { QualityWindow } from './QualityWindow'
import { SampleDataWindow } from './SampleDataWindow'
import { StatusLogWindow } from './StatusLogWindow'

/**
 * The five batch windows (F19-FR-01). Which one is open, and for which row, comes from the URL
 * (`?win=<name>&row=<row_key>`), so a window can be deep-linked; only one is open at a time.
 */
export function BatchWindows() {
  const { win, winRow, closeWindow } = useBatchView()
  if (!win || !winRow) return null
  const props = { rowKey: winRow, onClose: closeWindow }
  switch (win) {
    case 'inbound':
      return <InboundWindow {...props} />
    case 'quality':
      return <QualityWindow {...props} />
    case 'status':
      return <StatusLogWindow {...props} />
    case 'samples':
      return <SampleDataWindow {...props} />
    case 'needby':
      return <AdjustNeedsByWindow {...props} />
  }
}
