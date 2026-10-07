import type { EvidenceItem, Validator } from '../../api/agents'
import { withSiteTimes } from '../../lib/format'

const SYSTEM_TONE = { LIMS: 'bg-sky-50 text-sky-800', ERP: 'bg-violet-50 text-violet-800', QMS: 'bg-amber-50 text-amber-800' }

/** A system's name in a small badge: the "system icon" of F12-FR-12 c (a letter badge, no brand logo). */
export function SystemBadge({ system }: { system: EvidenceItem['system'] }) {
  return <span className={`inline-block rounded-chip px-1.5 py-px text-[11px] font-bold tracking-wide ${SYSTEM_TONE[system]}`}>{system}</span>
}

/** The evidence the ticket cites, each item with the validator's re-read of its source (V2): "verified ✓". */
export function EvidenceTable({ evidence, validator, timezone }: { evidence: EvidenceItem[]; validator: Validator | null; timezone: string }) {
  return (
    <table className="w-full text-[13px]" data-testid="evidence-table">
      <thead>
        <tr className="border-b border-hairline text-left text-[11px] tracking-wide text-ink-2 uppercase">
          <th className="py-1.5 pr-3 font-semibold">System</th>
          <th className="py-1.5 pr-3 font-semibold">Reference</th>
          <th className="py-1.5 pr-3 font-semibold">Field</th>
          <th className="py-1.5 pr-3 font-semibold">Value</th>
          <th className="py-1.5 font-semibold">Check</th>
        </tr>
      </thead>
      <tbody>
        {evidence.map((item, index) => {
          const check = validator?.evidence.find((e) => e.index === index)
          return (
            <tr key={`${item.system}-${item.ref}-${item.field}`} data-testid="evidence-row" className="border-b border-hairline/60">
              <td className="py-1.5 pr-3">
                <SystemBadge system={item.system} />
              </td>
              <td className="py-1.5 pr-3 font-mono">{item.ref}</td>
              <td className="py-1.5 pr-3 font-mono">{item.field}</td>
              <td className="py-1.5 pr-3 font-mono">{withSiteTimes(item.value, timezone)}</td>
              <td className="py-1.5" data-verified={check ? String(check.verified) : 'unknown'}>
                {check ? (
                  check.verified ? (
                    <span className="font-medium text-emerald-700">verified ✓</span>
                  ) : (
                    <span className="text-red-700" title={check.message}>
                      ✗ {check.message}
                    </span>
                  )
                ) : (
                  <span className="text-slate-400">—</span>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

/** The rules V1–V6 (and V0 when the run produced no ticket), each pass or fail with its message. */
export function ValidatorChecklist({ validator }: { validator: Validator }) {
  return (
    <ul className="space-y-1.5 text-[13px]" data-testid="validator-checklist">
      {validator.rules.map((rule) => (
        <li key={rule.id} data-testid={`rule-${rule.id}`} data-passed={String(rule.passed)} className="flex items-start gap-2">
          <span aria-hidden className={`mt-px font-bold ${rule.passed ? 'text-emerald-600' : 'text-red-600'}`}>
            {rule.passed ? '✓' : '✗'}
          </span>
          <span className="w-8 shrink-0 font-mono font-semibold">{rule.id}</span>
          <span>
            <span className="font-medium">{rule.name}.</span> <span className="text-ink-2">{rule.message}</span>
            <span className="sr-only">{rule.passed ? ' Passed.' : ' Failed.'}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}
