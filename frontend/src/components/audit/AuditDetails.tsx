import { formatDate, humanize } from '../../lib/format'

type Details = Record<string, unknown> | null

const FIELD_LABELS: Record<string, string> = {
  adjusted_need_by_date: 'Need-by',
  expedite: 'Expedite',
  manual_status: 'Status',
}

/** One value as a person would read it: dates in the 05 format, yes/no, a status as "AMBER · QC Lab". */
export function describeValue(field: string, value: unknown): string {
  if (value === null || value === undefined) return field === 'adjusted_need_by_date' ? 'system date' : 'none'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (field === 'manual_status' && typeof value === 'object') {
    const status = value as { rag?: string; team?: string }
    return `${(status.rag ?? '').toUpperCase()}${status.team ? ` · ${status.team}` : ''}`
  }
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value)
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return Object.entries(value as object).map(([k, v]) => `${k}: ${String(v)}`).join(', ')
  return String(value)
}

/** Labelled lines for an audit entry. Override rows read "Need-by: 3 Dec 2026 → 26 Nov 2026" (OQ-068). */
export function auditLines(details: Details): [string, string][] {
  if (!details) return []
  const lines: [string, string][] = []
  if ('field' in details && ('old' in details || 'new' in details)) {
    const field = String(details.field)
    lines.push([
      FIELD_LABELS[field] ?? humanize(field),
      `${describeValue(field, details.old)} → ${describeValue(field, details.new)}`,
    ])
    if (details.reason_code) lines.push(['Reason', humanize(String(details.reason_code))])
    if (details.note) lines.push(['Note', String(details.note)])
    return lines
  }
  for (const [key, value] of Object.entries(details)) lines.push([humanize(key), describeValue(key, value)])
  return lines
}

export function AuditDetails({ details }: { details: Details }) {
  const lines = auditLines(details)
  if (lines.length === 0) return <span className="text-slate-400">No details</span>
  return (
    <dl className="grid grid-cols-[8rem_1fr] gap-y-0.5 text-[13px]" data-testid="audit-details">
      {lines.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-slate-500">{label}</dt>
          <dd className="break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}
