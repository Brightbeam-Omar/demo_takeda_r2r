import type { Schemas } from '../../api/client'
import { formatDate, humanize } from '../../lib/format'

export type Explanation =
  | Schemas['StageExplain']
  | Schemas['CompletionExplain']
  | Schemas['MetricExplain']
  | Schemas['FlowExplain']

type Pair = [string, string]

const show = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '–'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) return formatDate(value)
  return String(value)
}

/** One list of label/value pairs per section; the same lists drive the screen and the copied text. */
export interface Section {
  title: string
  pairs: Pair[]
}

export interface Content {
  headline: string
  words: string
  sections: Section[]
  rows?: { columns: string[]; data: string[][] }
  sourceRefs?: unknown
  provenance: string
}

function provenance(f: Schemas['Freshness']): string {
  return `Pipeline run ${f.contract_run_id ?? 'unknown'}, published ${f.last_success_at ? formatDate(f.last_success_at) : 'unknown'}`
}

/** Turns an F09 explain payload into the plain structure the popover shows (and copies). */
export function describeExplanation(data: Explanation): Content {
  if (data.kind === 'stage') {
    return {
      headline: `Why ${data.stage_label}?`,
      words: `Rule ${data.rule.id}: ${data.rule.description}`,
      sections: [{ title: 'Inputs', pairs: Object.entries(data.input_values).map(([k, v]) => [humanize(k), show(v)] as Pair) }],
      sourceRefs: data.source_refs,
      provenance: provenance(data.freshness),
    }
  }
  if (data.kind === 'expected_completion') {
    const slas = Object.keys(data.effective_slas).map((stage) => {
      const base = data.base_slas[stage]
      const effective = data.effective_slas[stage]
      return [humanize(stage), base === effective ? `${effective} d` : `${base} d → ${effective} d`] as Pair
    })
    return {
      headline: 'How the expected completion is planned',
      words: data.formula,
      sections: [
        {
          title: 'Inputs',
          pairs: [
            ['Stage entry', show(data.entry_date)],
            ['System need-by', show(data.system_need_by)],
            ['Operative need-by', `${show(data.operative_need_by)}${data.need_by_adjusted ? ` (adjusted: ${humanize(data.adjusted_reason_code ?? '')})` : ''}`],
            ['Available days', show(data.available_days)],
            ['SLA budget', show(data.budget_days)],
            ['Compression', data.compressed ? `${Math.round(Number(data.compression_ratio) * 100)}%` : 'none'],
          ],
        },
        { title: 'SLAs (profile → effective)', pairs: slas },
        {
          title: 'Result',
          pairs: [
            ['Expected completion', show(data.expected_completion)],
            ['Days remaining', show(data.days_remaining)],
            ['RAG', data.rag ? data.rag.toUpperCase() : '–'],
          ],
        },
      ],
      provenance: provenance(data.freshness),
    }
  }
  if (data.kind === 'metric') {
    if (data.status !== 'active') {
      return {
        headline: `${data.metric_id} · ${data.label}`,
        words: data.null_reason ?? 'Awaiting signal',
        sections: [],
        provenance: provenance(data.freshness),
      }
    }
    return {
      headline: `${data.metric_id} · ${data.label}`,
      words: `${data.on_time} of ${data.completed} lots completed on time in the week of ${show(data.week_start)} (${data.pct ?? '–'}%), against an SLA of ${data.sla_days} days.`,
      sections: [
        {
          title: 'Figure',
          pairs: [
            ['Week starting', show(data.week_start)],
            ['Completed', show(data.completed)],
            ['On time', show(data.on_time)],
            ['SLA', `${show(data.sla_days)} d`],
          ],
        },
      ],
      rows: {
        columns: ['Lot', 'Entered', 'Left', 'Days', 'SLA', 'On time'],
        data: data.rows.map((r) => [r.row_key, show(r.entry_date), show(r.exit_date), show(r.duration_days), show(r.sla_days), show(r.on_time)]),
      },
      provenance: provenance(data.freshness),
    }
  }
  return {
    headline: `${data.stage_label}: ${data.count}`,
    words: `${data.count} lots are in ${data.stage_label} (${data.mode === 'snapshot' ? 'snapshot of all dates' : 'due in the selected period'}), placed there by ${data.rules.map((r) => r.id).join(', ')}.`,
    sections: [
      {
        title: 'Rules',
        pairs: data.rules.map((r) => [r.id, r.description] as Pair),
      },
      {
        title: 'Filters',
        pairs: Object.entries(data.filters).map(([k, v]) => [humanize(k), Array.isArray(v) ? (v.length ? v.join(', ') : '–') : show(v)] as Pair),
      },
    ],
    rows: { columns: ['Lot'], data: data.row_keys.map((k) => [k]) },
    provenance: provenance(data.freshness),
  }
}

export function toPlainText(content: Content): string {
  const lines = [content.headline, content.words, '']
  for (const section of content.sections) {
    lines.push(section.title)
    for (const [label, value] of section.pairs) lines.push(`  ${label}: ${value}`)
  }
  if (content.rows) {
    lines.push('', content.rows.columns.join('\t'))
    for (const row of content.rows.data) lines.push(row.join('\t'))
  }
  lines.push('', content.provenance)
  return lines.join('\n')
}

export function ExplainBody({ content }: { content: Content }) {
  return (
    <div className="space-y-3 text-[13px]" data-testid="explain-body">
      <div>
        <h4 className="font-semibold text-slate-900">{content.headline}</h4>
        <p className="mt-1 text-slate-700">{content.words}</p>
      </div>
      {content.sections.map((section) => (
        <div key={section.title}>
          <div className="mb-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">{section.title}</div>
          <dl className="grid grid-cols-[10rem_1fr] gap-x-3 gap-y-0.5">
            {section.pairs.map(([label, value]) => (
              <div key={label} className="contents">
                <dt className="text-slate-500">{label}</dt>
                <dd className="break-words">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
      {content.rows ? (
        <div>
          <div className="mb-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Contributing lots ({content.rows.data.length})
          </div>
          <div className="max-h-48 overflow-auto rounded-chip border border-slate-200">
            <table className="w-full text-left text-xs" data-testid="explain-rows">
              <thead className="sticky top-0 bg-slate-50 text-slate-500">
                <tr>
                  {content.rows.columns.map((column) => (
                    <th key={column} className="px-2 py-1 font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {content.rows.data.map((row) => (
                  <tr key={row[0]} className="border-t border-slate-100">
                    {row.map((cell, index) => (
                      <td key={index} className="px-2 py-1">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {content.sourceRefs ? (
        <details>
          <summary className="cursor-pointer text-slate-600">Source references</summary>
          <pre className="mt-1 overflow-auto rounded-chip bg-slate-50 p-2 text-xs">{JSON.stringify(content.sourceRefs, null, 2)}</pre>
        </details>
      ) : null}
      <p className="border-t border-slate-100 pt-2 text-xs text-slate-500">{content.provenance}</p>
    </div>
  )
}
