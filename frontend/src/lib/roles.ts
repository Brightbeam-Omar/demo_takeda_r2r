/** Who may write what. The server enforces this (F09-FR-05); the UI only mirrors it to disable controls. */
export const READ_ONLY_HINT = 'Read-only role'

export const canEditNeedBy = (role: string | undefined) => role === 'planner' || role === 'admin'
export const canSetStatus = (role: string | undefined) =>
  role === 'qc_lead' || role === 'qa_release' || role === 'admin'
export const canComment = (role: string | undefined) => role !== undefined && role !== 'viewer'
