import { useMemo } from 'react'
import type { Reference, Row } from '../../api/queries'
import type { Filters } from '../../state/url-filters'
import { CampaignPills } from './CampaignPills'
import { PillRow } from './PillRow'

/** The reserved class key for rows whose class is NULL (OQ-086). It is not in the profile. */
export const UNKNOWN_CLASS = 'unknown'

interface Props {
  reference: Reference | undefined
  rows: Row[]
  filters: Filters
  onChange: (patch: Partial<Filters>) => void
}

/** The expanded panel (F16-FR-02): Type, Class and Campaign rows. Same filter semantics as before (OQ-059). */
export function FilterPanel({ reference, rows, filters, onChange }: Props) {
  const counts = useMemo(() => {
    const campaigns = new Map<string, number>()
    let unknown = 0
    for (const row of rows) {
      if (row.campaign) campaigns.set(row.campaign, (campaigns.get(row.campaign) ?? 0) + 1)
      if (!row.material_class) unknown += 1
    }
    return { campaigns, unknown }
  }, [rows])

  return (
    <div id="filter-panel" className="space-y-3 rounded-card border border-slate-200 bg-slate-50 p-4">
      <PillRow
        label="Type"
        options={(reference?.molecule_types ?? []).map((item) => ({ value: item.key, label: item.label }))}
        selected={filters.types}
        onChange={(types) => onChange({ types })}
      />
      <PillRow
        label="Class"
        options={[
          ...(reference?.classes ?? []).map((item) => ({ value: item.key, label: item.label })),
          { value: UNKNOWN_CLASS, label: 'Unknown', count: counts.unknown },
        ]}
        selected={filters.classes}
        onChange={(classes) => onChange({ classes })}
      />
      <CampaignPills
        campaigns={(reference?.campaigns ?? []).map((value) => ({ value, label: value, count: counts.campaigns.get(value) ?? 0 }))}
        selected={filters.campaigns}
        onChange={(campaigns) => onChange({ campaigns })}
      />
    </div>
  )
}
