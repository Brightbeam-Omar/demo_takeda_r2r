import { useTerms } from '../../hooks/useTerms'
import { flagChips } from '../../lib/flags'
import type { Filters } from '../../state/url-filters'

interface Props {
  flags: string[]
  onChange: (patch: Partial<Filters>) => void
}

/** F10's inline tag chips, kept until F17's tag row replaces them (OQ-085). */
export function TagChips({ flags, onChange }: Props) {
  const terms = useTerms()
  const toggle = (keys: string[]) => {
    const on = keys.every((key) => flags.includes(key))
    const rest = flags.filter((flag) => !keys.includes(flag))
    onChange({ flags: on ? rest : [...rest, ...keys] })
  }
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Tags">
      {flagChips(terms).map((chip) => {
        const on = chip.keys.every((key) => flags.includes(key))
        return (
          <button
            key={chip.label}
            type="button"
            aria-pressed={on}
            className={`rounded-chip border px-2 py-1 text-xs font-semibold tracking-wide ${on ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'}`}
            onClick={() => toggle(chip.keys)}
          >
            {chip.label}
          </button>
        )
      })}
    </div>
  )
}
