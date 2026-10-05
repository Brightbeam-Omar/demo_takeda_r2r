import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useDeletePreset, useOverwritePreset, usePresets, useSavePreset } from '../../api/queries'
import { ApiError } from '../../api/client'
import { parseFilters, serializeFilters, type Filters } from '../../state/url-filters'
import { useToast } from '../common/Toasts'

interface Props {
  filters: Filters
  /** Applying a preset replaces the whole URL filter state (F16-FR-05). */
  onApply: (filters: Filters) => void
}

const MAX_NAME = 60

/** `⚲ Presets`: the user's saved filters, plus "+ Save current filters" (F16-FR-05, OQ-089). */
export function PresetsMenu({ filters, onApply }: Props) {
  const [open, setOpen] = useState(false)
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState('')
  const [replacing, setReplacing] = useState<string | null>(null) // the duplicate name awaiting a yes
  const root = useRef<HTMLDivElement>(null)
  const presets = usePresets()
  const save = useSavePreset()
  const overwrite = useOverwritePreset()
  const remove = useDeletePreset()
  const { notify } = useToast()

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const reset = () => {
    setNaming(false)
    setName('')
    setReplacing(null)
  }
  // Once a preset is saved the menu has done its job; leaving it open would cover the chips below it.
  const finish = () => {
    reset()
    setOpen(false)
  }
  // Stored literally, so a "this_week" preset stays relative (OQ-089).
  const query = serializeFilters(filters).toString()
  const fail = (error: Error) => notify(`Could not save the preset: ${error.message}`, 'error')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    save.mutate(
      { name: trimmed, query },
      {
        onSuccess: () => {
          notify(`Saved preset “${trimmed}”`)
          finish()
        },
        onError: (error) => (error instanceof ApiError && error.status === 409 ? setReplacing(trimmed) : fail(error)),
      },
    )
  }

  const replace = () => {
    const existing = presets.data?.find((preset) => preset.name === replacing)
    if (!existing) return reset()
    overwrite.mutate(
      { id: existing.id, query },
      {
        onSuccess: () => {
          notify(`Replaced preset “${existing.name}”`)
          finish()
        },
        onError: fail,
      },
    )
  }

  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:border-slate-400"
        onClick={() => setOpen(!open)}
      >
        ⚲ Presets
      </button>
      {open && (
        <div role="menu" aria-label="Presets" className="absolute z-20 mt-1 w-72 rounded-card border border-slate-200 bg-white p-2 shadow-lg">
          {presets.data && presets.data.length === 0 && <p className="px-2 py-1 text-sm text-slate-500">No saved presets</p>}
          <ul>
            {(presets.data ?? []).map((preset) => (
              <li key={preset.id} className="flex items-center gap-1 rounded-chip hover:bg-slate-50">
                <button
                  type="button"
                  role="menuitem"
                  className="flex-1 truncate px-2 py-1 text-left text-sm"
                  onClick={() => {
                    onApply(parseFilters(new URLSearchParams(preset.query)))
                    setOpen(false)
                  }}
                >
                  {preset.name}
                </button>
                <button
                  type="button"
                  aria-label={`Delete preset ${preset.name}`}
                  className="rounded-chip px-2 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
                  onClick={() => remove.mutate(preset.id, { onError: (error) => notify(`Could not delete the preset: ${error.message}`, 'error') })}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-1 border-t border-slate-100 pt-1">
            {replacing ? (
              <div role="alertdialog" aria-label="Replace existing preset?" className="space-y-2 px-2 py-1 text-sm">
                <p>Replace existing preset? “{replacing}” already exists.</p>
                <div className="flex gap-2">
                  <button type="button" className="rounded-chip bg-indigo-600 px-3 py-1 text-white" onClick={replace}>
                    Replace
                  </button>
                  <button type="button" className="rounded-chip border border-slate-300 px-3 py-1" onClick={() => setReplacing(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : naming ? (
              <form onSubmit={submit} className="flex gap-2 px-2 py-1">
                <input
                  autoFocus
                  aria-label="Preset name"
                  maxLength={MAX_NAME}
                  placeholder="Preset name"
                  className="min-w-0 flex-1 rounded-chip border border-slate-300 px-2 py-1 text-sm"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
                <button type="submit" disabled={!name.trim() || save.isPending} className="rounded-chip bg-indigo-600 px-3 py-1 text-sm text-white disabled:opacity-50">
                  Save
                </button>
              </form>
            ) : (
              <button type="button" role="menuitem" className="w-full rounded-chip px-2 py-1 text-left text-sm text-indigo-600 hover:bg-slate-50" onClick={() => setNaming(true)}>
                + Save current filters
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
