import { useState } from 'react'
import { MultiSelect } from './MultiSelect'
import { pillClass, type PillOption } from './PillRow'

export type CampaignView = 'pills' | 'dropdown'

const VIEW_KEY = 'r2r.campaignView'

/** The pills or the dropdown, remembered for the browser session (F16-FR-02). */
export function useCampaignView(): [CampaignView, (view: CampaignView) => void] {
  const [view, setView] = useState<CampaignView>(() => (sessionStorage.getItem(VIEW_KEY) === 'dropdown' ? 'dropdown' : 'pills'))
  const choose = (next: CampaignView) => {
    sessionStorage.setItem(VIEW_KEY, next)
    setView(next)
  }
  return [view, choose]
}

interface Props {
  campaigns: PillOption[]
  selected: string[]
  onChange: (selected: string[]) => void
}

/** Campaign filter: live-count pills with a search box in a scroll area of at most three rows, or one multi-select. */
export function CampaignPills({ campaigns, selected, onChange }: Props) {
  const [view, setView] = useCampaignView()
  const [term, setTerm] = useState('')
  const shown = campaigns.filter((option) => option.label.toLowerCase().includes(term.toLowerCase()))
  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])
  return (
    <div role="group" aria-label="Campaign" className="flex items-start gap-3">
      <span className="w-20 shrink-0 pt-1 text-sm font-semibold text-slate-500">Campaign</span>
      <div className="flex flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {view === 'pills' && (
            <input
              type="search"
              aria-label="Filter campaigns"
              placeholder="Filter campaigns…"
              className="w-48 rounded-chip border border-slate-300 bg-white px-2 py-1 text-sm"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
            />
          )}
          {view === 'dropdown' && <MultiSelect label="All campaigns" options={campaigns} selected={selected} onChange={onChange} searchable />}
          <button
            type="button"
            className="rounded-chip px-2 py-1 text-sm text-indigo-600 hover:text-indigo-800"
            onClick={() => setView(view === 'pills' ? 'dropdown' : 'pills')}
          >
            {view === 'pills' ? '▤ Dropdown view' : '▤ Pill view'}
          </button>
        </div>
        {view === 'pills' && (
          <div data-testid="campaign-pills" className="flex max-h-[6.5rem] flex-wrap items-start gap-2 overflow-y-auto">
            <button type="button" aria-pressed={selected.length === 0} className={pillClass(selected.length === 0)} onClick={() => onChange([])}>
              All
            </button>
            {shown.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={selected.includes(option.value)}
                className={pillClass(selected.includes(option.value))}
                onClick={() => toggle(option.value)}
              >
                {option.label}
                <span className="ml-1.5 text-xs text-slate-500">{option.count ?? 0}</span>
              </button>
            ))}
            {shown.length === 0 && <span className="py-1 text-sm text-slate-500">No campaigns match</span>}
          </div>
        )}
      </div>
    </div>
  )
}
