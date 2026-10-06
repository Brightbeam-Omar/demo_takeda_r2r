import { useMemo, useState } from 'react'
import { useContractSchema } from '../../api/queries'
import { PageIntro } from '../../components/admin/PageIntro'
import { ErrorState, Skeleton } from '../../components/common/States'

/** Schema Reference (F21-FR-06): every published object with its grain and its typed, described columns. */
export function SchemaReference() {
  const schema = useContractSchema()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set())
  const needle = q.trim().toLowerCase()

  const shown = useMemo(() => {
    const objects = schema.data?.objects ?? []
    if (!needle) return objects.map((object) => ({ object, columns: object.columns, matched: false }))
    return objects
      .map((object) => {
        const nameHit = object.name.toLowerCase().includes(needle) || object.description.toLowerCase().includes(needle)
        const columns = object.columns.filter((column) => `${column.name} ${column.description}`.toLowerCase().includes(needle))
        return { object, columns: nameHit ? object.columns : columns, matched: nameHit || columns.length > 0 }
      })
      .filter((entry) => entry.matched)
  }, [schema.data, needle])

  const toggle = (name: string) =>
    setOpen((current) => {
      const next = new Set(current)
      if (!next.delete(name)) next.add(name)
      return next
    })

  return (
    <main className="flex-1 space-y-3 overflow-auto p-6 pb-20" data-testid="schema-reference-page">
      <PageIntro subtitle="The published contract: the read-only objects the application mirrors, with their grain and columns" />
      <input
        aria-label="Search the schema"
        placeholder="Search objects and columns…"
        value={q}
        onChange={(event) => setQ(event.target.value)}
        className="w-80 rounded-chip border border-slate-300 bg-white px-3 py-1.5 text-sm"
      />
      {schema.isError ? <ErrorState what="the schema" error={schema.error} onRetry={() => void schema.refetch()} /> : null}
      {schema.isPending ? <Skeleton label="schema" height="h-48" /> : null}
      {schema.data && shown.length === 0 ? <p className="text-sm text-ink-2">Nothing matches “{q}”.</p> : null}
      <ul className="space-y-2">
        {shown.map(({ object, columns }) => {
          const expanded = open.has(object.name) || needle !== ''
          return (
            <li key={object.name} data-testid="schema-object" data-object={object.name} className="rounded-card border border-hairline bg-white">
              <button
                type="button"
                aria-expanded={expanded}
                className="flex w-full items-start gap-3 px-4 py-3 text-left"
                onClick={() => toggle(object.name)}
              >
                <span aria-hidden className="mt-0.5 text-ink-2">
                  {expanded ? '▾' : '▸'}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="font-mono text-sm font-semibold text-ink">{object.name}</span>
                  <span className="ml-2 text-xs text-ink-2">{object.columns.length} columns</span>
                  <span className="mt-0.5 block text-[13px] text-ink-2">{object.description}</span>
                  <span className="mt-0.5 block text-xs text-ink-2">Grain: {object.grain}</span>
                </span>
              </button>
              {expanded ? (
                <table className="w-full border-t border-hairline text-left text-[13px]" data-testid="schema-columns">
                  <thead className="text-[11px] tracking-wider text-ink-2 uppercase">
                    <tr>
                      <th className="px-4 py-1.5 font-semibold">Column</th>
                      <th className="font-semibold">Type</th>
                      <th className="px-4 font-semibold">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {columns.map((column) => (
                      <tr key={column.name} data-testid="schema-column" className="border-t border-hairline align-top">
                        <td className="px-4 py-1.5 font-mono">{column.name}</td>
                        <td className="font-mono text-ink-2">{column.type}</td>
                        <td className="px-4 whitespace-normal text-ink">{column.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </li>
          )
        })}
      </ul>
    </main>
  )
}
