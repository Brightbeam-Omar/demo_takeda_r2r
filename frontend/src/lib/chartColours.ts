/** Chart colours as literal values: SVG fills do not resolve `var()` reliably. Same hues as the tokens in index.css. */
export const RAG_HEX: Record<string, string> = {
  green: '#16A34A',
  amber: '#D97706',
  red: '#DC2626',
  grey: '#9CA3AF',
}

const STAGE_HEX = ['#0ea5e9', '#06b6d4', '#14b8a6', '#10b981', '#84cc16', '#f59e0b', '#f97316', '#8b5cf6']

/** The stage hue by its 1-based position in the profile, as the stage cards and badges do (05 v2 section 2). */
export function stageHex(sort: number): string {
  return STAGE_HEX[(sort - 1) % STAGE_HEX.length]!
}

export const INK_2 = '#6b7280'
export const HAIRLINE = '#e5e7eb'
export const ACCENT = '#4f46e5'
